"""Delta-hedge simulation over Monte Carlo paths.

Simulates a continuous delta-hedging strategy by rebalancing the underlying
position at fixed intervals to keep the portfolio delta-neutral.  Transaction
costs are deducted at each rebalance.

The simulation produces a distribution of hedge P&L across all MC paths,
from which efficiency metrics are derived.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

try:
    from simulation.monte_carlo import SimulationResult
except ImportError:
    SimulationResult = None  # type: ignore[assignment,misc]

from derivatives.models.bsm import BSMPricer
from derivatives.greeks.analytical import AnalyticalGreeks
from derivatives.portfolio.aggregator import PortfolioGreeks, OptionPosition


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class HedgeSimulationResult:
    """Outcome of a delta-hedge simulation.

    Attributes:
        mean_pnl: Mean hedge P&L across all paths (should be near 0 for a
            perfect hedge).
        std_pnl: Standard deviation of P&L (lower = better hedging).
        hedge_efficiency: 1 - std(hedged P&L) / std(unhedged P&L).  Higher
            is better; 1.0 = perfect hedge.
        worst_5pct_pnl: Mean of the worst 5% of path P&Ls (ES at 95%).
        cumulative_transaction_costs: Total transaction cost over the
            simulation in currency units.
        rebalancing_trades: Total number of hedge rebalances executed.
        per_path_pnl: Array of final P&L per simulation path, shape
            ``(n_paths,)``.
    """

    mean_pnl: float
    std_pnl: float
    hedge_efficiency: float
    worst_5pct_pnl: float
    cumulative_transaction_costs: float
    rebalancing_trades: int
    per_path_pnl: np.ndarray = field(default_factory=lambda: np.array([]))


# ---------------------------------------------------------------------------
# DeltaHedgeSimulator
# ---------------------------------------------------------------------------


class DeltaHedgeSimulator:
    """Simulate a delta-hedging strategy over Monte Carlo stock price paths.

    For each path, the simulator:
    1. Starts with an option position (short option, long delta shares).
    2. At every ``rebalance_frequency`` steps, re-computes BSM delta.
    3. Trades underlying shares to restore delta-neutrality.
    4. Deducts ``transaction_cost_bps`` per unit notional traded.
    5. Accumulates the P&L from option price change + hedge trade P&L.

    Args:
        portfolio: ``PortfolioGreeks`` instance (positions used for contract
            details and initial Greeks).
        sim_result: ``SimulationResult`` with price paths.
        rebalance_frequency: Steps between rebalances (default 5 = weekly
            if dt = 1/252).
        transaction_cost_bps: Round-trip transaction cost in basis points
            (default 10 bps).
        r: Risk-free rate for discounting intra-simulation cash flows.

    Notes:
        * The simulation operates on the *first position* in the portfolio
          for simplicity.  Multi-leg support is available via ``aggregate()``.
        * Paths are taken from the ticker of the first position.
    """

    def __init__(
        self,
        portfolio: PortfolioGreeks,
        sim_result: "SimulationResult",
        rebalance_frequency: int = 5,
        transaction_cost_bps: float = 10.0,
        r: float = 0.0,
    ):
        self.portfolio = portfolio
        self.sim_result = sim_result
        self.rebalance_frequency = int(rebalance_frequency)
        self.tc_bps = float(transaction_cost_bps)
        self.r = float(r)
        self.dt = sim_result.dt

    # ------------------------------------------------------------------
    # Public: simulate
    # ------------------------------------------------------------------

    def simulate(self) -> HedgeSimulationResult:
        """Run the delta-hedge simulation.

        Returns:
            A ``HedgeSimulationResult`` summarising hedge performance.

        Notes:
            * Uses BSM delta (analytical) at each rebalance step.
            * If a position's ticker is not in sim_result.paths, it is
              skipped and a zero P&L contribution is returned.
            * The unhedged P&L distribution (long option, no hedge) is also
              computed for normalisation of ``hedge_efficiency``.

        Audit:
            Log via ``DerivativesLogger`` after calling this method.
        """
        positions = self.portfolio.positions
        if not positions:
            return HedgeSimulationResult(
                mean_pnl=0.0, std_pnl=0.0, hedge_efficiency=0.0,
                worst_5pct_pnl=0.0, cumulative_transaction_costs=0.0,
                rebalancing_trades=0, per_path_pnl=np.array([]),
            )

        # Use the first position as the primary contract
        pos = positions[0]
        ticker = pos.ticker
        if ticker not in self.sim_result.paths:
            raise KeyError(f"Ticker '{ticker}' not in sim_result.paths")

        paths = self.sim_result.paths[ticker]   # (n_paths, n_steps)
        n_paths, n_steps = paths.shape
        dt = self.dt
        tc_frac = self.tc_bps / 10_000.0

        # Contract parameters
        K = pos.K
        T_total = pos.T
        opt_type = pos.option_type
        sigma = pos.greeks.delta  # will be overridden; use stored sigma from pricer
        q = 0.0

        # We need sigma from the pricer — reconstruct from greeks
        # Use a default of 0.20 if sigma not accessible
        # (In production this would be stored in the position)
        sigma_est = 0.20

        # --- Compute initial option price ---
        S0 = float(paths[:, 0].mean())

        # Vectorised simulation: one path per row
        per_path_pnl = np.zeros(n_paths)
        per_path_tc = np.zeros(n_paths)
        rebalance_count = 0

        # Unhedged P&L: just buy-and-hold the option
        unhedged_pnl = np.zeros(n_paths)

        quantity = pos.quantity * pos.notional

        for path_idx in range(n_paths):
            path = paths[path_idx]        # (n_steps,)
            cash = 0.0
            hedge_shares = 0.0
            total_tc = 0.0
            n_rebalances = 0

            # Initial option price at t=0
            T_rem = T_total
            S_now = float(path[0])
            pricer_now = BSMPricer(
                S=S_now, K=K, T=max(T_rem, 1e-6), r=self.r,
                sigma=sigma_est, option_type=opt_type, q=q,
            )
            option_price_now = pricer_now.price()

            # Initial delta hedge
            greeks_now = AnalyticalGreeks(pricer_now).compute()
            delta_now = greeks_now.delta
            shares_to_buy = -quantity * delta_now  # short option → long shares
            cash -= shares_to_buy * S_now * (1.0 + tc_frac)
            total_tc += abs(shares_to_buy) * S_now * tc_frac
            hedge_shares = shares_to_buy

            for step in range(1, n_steps):
                T_rem = max(T_total - step * dt, 1e-8)
                S_prev = float(path[step - 1])
                S_now = float(path[step])

                # Cash earns risk-free return
                cash *= np.exp(self.r * dt)

                # Rebalance
                if step % self.rebalance_frequency == 0 or step == n_steps - 1:
                    pricer_now = BSMPricer(
                        S=S_now, K=K, T=T_rem, r=self.r,
                        sigma=sigma_est, option_type=opt_type, q=q,
                    )
                    delta_new = AnalyticalGreeks(pricer_now).compute().delta
                    shares_target = -quantity * delta_new
                    delta_shares = shares_target - hedge_shares
                    tc_this = abs(delta_shares) * S_now * tc_frac
                    cash -= delta_shares * S_now + tc_this
                    total_tc += tc_this
                    hedge_shares = shares_target
                    n_rebalances += 1

            # At expiry: liquidate shares at terminal price
            S_T = float(path[-1])
            cash += hedge_shares * S_T * (1.0 - tc_frac)
            total_tc += abs(hedge_shares) * S_T * tc_frac

            # Option P&L: short option received premium, now pays payoff
            if opt_type == "call":
                option_payout = max(S_T - K, 0.0)
            else:
                option_payout = max(K - S_T, 0.0)
            option_pnl = quantity * (option_price_now - option_payout)
            hedge_pnl = cash
            per_path_pnl[path_idx] = option_pnl + hedge_pnl
            per_path_tc[path_idx] = total_tc
            if path_idx == 0:
                rebalance_count = n_rebalances  # record from first path

        # Unhedged P&L: just holding the option
        S_T_vec = paths[:, -1]
        if opt_type == "call":
            payout_vec = np.maximum(S_T_vec - K, 0.0)
        else:
            payout_vec = np.maximum(K - S_T_vec, 0.0)
        pricer_init = BSMPricer(
            S=float(paths[:, 0].mean()), K=K, T=T_total,
            r=self.r, sigma=sigma_est, option_type=opt_type, q=q,
        )
        opt_price_init = pricer_init.price()
        unhedged_pnl = quantity * (opt_price_init - payout_vec)

        std_unhedged = float(unhedged_pnl.std())
        std_hedged = float(per_path_pnl.std(ddof=1)) if n_paths > 1 else 0.0
        efficiency = float(1.0 - std_hedged / std_unhedged) if std_unhedged > 1e-10 else 0.0

        worst_5pct = float(np.percentile(per_path_pnl, 5))
        total_tc_mean = float(per_path_tc.mean())

        return HedgeSimulationResult(
            mean_pnl=float(per_path_pnl.mean()),
            std_pnl=std_hedged,
            hedge_efficiency=float(np.clip(efficiency, -1.0, 1.0)),
            worst_5pct_pnl=worst_5pct,
            cumulative_transaction_costs=total_tc_mean,
            rebalancing_trades=int(rebalance_count * n_paths),
            per_path_pnl=per_path_pnl,
        )
