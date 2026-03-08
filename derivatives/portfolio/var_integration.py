"""Options VaR integration — delta-gamma approximation + full revaluation.

Composes ``PortfolioVaR`` from the risk module with option-specific
price sensitivities to produce an options-aware VaR/CVaR estimate.

Two methods:
* **Delta-Gamma**: Uses first- and second-order Taylor expansion to map
  underlying scenario shocks to option P&L.  Fast; accurate for small moves.
* **Full Revaluation**: Re-prices all options under each scenario.  Slower;
  captures non-linear payoff structure accurately for large moves.

Stressed scenarios:
    * ``"flash_crash"``: S drops 15%, vol spikes +30%.
    * ``"vol_spike"``: S unchanged, vol spikes +50%.
    * ``"rate_shock"``: S unchanged, rates +200bps.
    * ``"market_crash"``: S drops 25%, vol spikes +40%.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from derivatives.portfolio.aggregator import PortfolioGreeks, OptionPosition
from derivatives.models.bsm import BSMPricer

try:
    from risk.var_cvar import PortfolioVaR, VaRResult
except ImportError:
    PortfolioVaR = None   # type: ignore[assignment,misc]
    VaRResult = None      # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class OptionsVaRResult:
    """Result of an options-aware VaR computation.

    Attributes:
        var: Value-at-Risk (positive loss fraction).
        cvar: Conditional VaR / Expected Shortfall (positive).
        method: Description of the method used.
        confidence: Confidence level (e.g. 0.99).
        horizon_days: Holding period in days.
        n_scenarios: Number of scenarios used.
        stressed_scenario: Name of stress scenario (``None`` for normal VaR).
    """

    var: float
    cvar: float
    method: str
    confidence: float
    horizon_days: int
    n_scenarios: int
    stressed_scenario: Optional[str]


# ---------------------------------------------------------------------------
# Stress scenario definitions
# ---------------------------------------------------------------------------

_STRESS_SCENARIOS: Dict[str, Dict[str, float]] = {
    "flash_crash":    {"dS_pct": -0.15, "dvol_abs": +0.30, "dr_abs": 0.0},
    "vol_spike":      {"dS_pct":  0.00, "dvol_abs": +0.50, "dr_abs": 0.0},
    "rate_shock":     {"dS_pct":  0.00, "dvol_abs":  0.00, "dr_abs": +0.02},
    "market_crash":   {"dS_pct": -0.25, "dvol_abs": +0.40, "dr_abs": 0.0},
}


# ---------------------------------------------------------------------------
# OptionsVaR
# ---------------------------------------------------------------------------


class OptionsVaR:
    """Compute options-aware VaR/CVaR by composing with PortfolioVaR.

    Args:
        positions: List of ``OptionPosition`` objects in the book.
        portfolio_var: A calibrated ``PortfolioVaR`` instance whose scenario
            P&L distribution is used as the underlying shock distribution.
        r: Risk-free rate (used for full-revaluation re-pricing).

    Notes:
        The underlying scenario P&L distribution from ``portfolio_var`` is
        interpreted as *fractional returns* of the underlying assets.  These
        are mapped to option P&L via delta-gamma or full-revaluation.
    """

    def __init__(
        self,
        positions: List[OptionPosition],
        portfolio_var: "PortfolioVaR",
        r: float = 0.0,
    ):
        self.positions = positions
        self.portfolio_var = portfolio_var
        self.r = float(r)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _underlying_returns(self) -> np.ndarray:
        """Extract scenario fractional returns from the underlying PortfolioVaR.

        Returns:
            Array of fractional returns (shape: n_scenarios,).
        """
        pnl = self.portfolio_var.get_scenario_pnl_distribution()
        # Interpret PnL as fractional returns (assumes initial portfolio
        # value of 1.0 for normalisation)
        return pnl

    def _delta_gamma_pnl(self, returns: np.ndarray) -> np.ndarray:
        """Compute option book P&L using delta-gamma approximation.

        ΔV ≈ Δ * ΔS + 0.5 * Γ * ΔS²

        Args:
            returns: Fractional returns array (n_scenarios,).

        Returns:
            Option book P&L array (n_scenarios,).
        """
        total_pnl = np.zeros(len(returns))
        for pos in self.positions:
            w = pos.quantity * pos.notional
            g = pos.greeks
            dS = returns * pos.K   # approximate ΔS = return * S_proxy
            option_pnl = w * (g.delta * dS + 0.5 * g.gamma * dS ** 2)
            total_pnl += option_pnl
        return total_pnl

    def _full_revaluation_pnl(self, returns: np.ndarray) -> np.ndarray:
        """Compute option book P&L by full re-pricing under each scenario.

        Re-prices each option using BSM at S_shocked = S * (1 + return).

        Args:
            returns: Fractional returns array (n_scenarios,).

        Returns:
            Option book P&L array (n_scenarios,).
        """
        total_pnl = np.zeros(len(returns))
        for pos in self.positions:
            w = pos.quantity * pos.notional
            S_base = pos.K   # proxy for S
            sigma_base = 0.20   # default; ideally stored in position

            # Current option value
            try:
                pricer_base = BSMPricer(
                    S=S_base, K=pos.K, T=max(pos.T, 1e-6),
                    r=self.r, sigma=sigma_base,
                    option_type=pos.option_type,
                )
                v_base = pricer_base.price()
            except Exception:
                v_base = 0.0

            # Vectorise: compute shocked prices
            S_shocked = S_base * (1.0 + returns)
            pnl_vec = np.zeros(len(returns))
            for idx, S_s in enumerate(S_shocked):
                S_s = max(float(S_s), 1e-6)
                try:
                    pricer_s = BSMPricer(
                        S=S_s, K=pos.K, T=max(pos.T, 1e-6),
                        r=self.r, sigma=sigma_base,
                        option_type=pos.option_type,
                    )
                    pnl_vec[idx] = pricer_s.price() - v_base
                except Exception:
                    pnl_vec[idx] = 0.0
            total_pnl += w * pnl_vec
        return total_pnl

    def _var_from_pnl(
        self,
        pnl: np.ndarray,
        confidence: float,
        horizon_days: int,
        method: str,
        stressed_scenario: Optional[str] = None,
    ) -> OptionsVaRResult:
        """Compute VaR/CVaR from a P&L array.

        Args:
            pnl: Scenario P&L array.
            confidence: Confidence level.
            horizon_days: Holding period.
            method: Method label.
            stressed_scenario: Optional scenario name.

        Returns:
            ``OptionsVaRResult``.
        """
        scaled_pnl = pnl * np.sqrt(horizon_days)
        var = float(-np.percentile(scaled_pnl, (1 - confidence) * 100))
        tail = scaled_pnl[scaled_pnl <= -var]
        cvar = float(-tail.mean()) if len(tail) > 0 else var
        return OptionsVaRResult(
            var=var,
            cvar=cvar,
            method=method,
            confidence=confidence,
            horizon_days=horizon_days,
            n_scenarios=int(len(pnl)),
            stressed_scenario=stressed_scenario,
        )

    # ------------------------------------------------------------------
    # Public: compute
    # ------------------------------------------------------------------

    def compute(
        self,
        confidence: float = 0.99,
        horizon_days: int = 1,
    ) -> OptionsVaRResult:
        """Compute options VaR using both delta-gamma and full revaluation.

        Returns the *higher* (more conservative) of the two estimates.

        Args:
            confidence: Confidence level (default 0.99).
            horizon_days: Holding period in days (default 1).

        Returns:
            ``OptionsVaRResult`` using the more conservative method.

        Notes:
            * Delta-gamma is fast and accurate for small underlying moves.
            * Full revaluation captures non-linearity for large moves.
            * The maximum VaR of the two is returned as a conservative bound.
        """
        returns = self._underlying_returns()

        # Delta-gamma
        pnl_dg = self._delta_gamma_pnl(returns)
        result_dg = self._var_from_pnl(
            pnl_dg, confidence, horizon_days, "delta_gamma"
        )

        # Full revaluation (on a subset for speed if large)
        n_sample = min(len(returns), 2000)
        idx = np.random.choice(len(returns), n_sample, replace=False)
        pnl_fr = self._full_revaluation_pnl(returns[idx])
        result_fr = self._var_from_pnl(
            pnl_fr, confidence, horizon_days, "full_revaluation"
        )

        # Return the more conservative estimate
        if result_fr.var >= result_dg.var:
            return result_fr
        return result_dg

    # ------------------------------------------------------------------
    # Public: stressed_var
    # ------------------------------------------------------------------

    def stressed_var(self, scenario: str) -> OptionsVaRResult:
        """Compute VaR under a named stress scenario.

        Args:
            scenario: One of ``"flash_crash"``, ``"vol_spike"``,
                ``"rate_shock"``, ``"market_crash"``.

        Returns:
            ``OptionsVaRResult`` for the stressed scenario.

        Raises:
            ValueError: If ``scenario`` is not one of the four supported names.

        Notes:
            Stress scenarios apply a deterministic shift to all underlying
            prices and vol levels.  The scenario P&L is computed via full
            revaluation under the shocked parameters.
        """
        if scenario not in _STRESS_SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario}'. "
                f"Valid: {list(_STRESS_SCENARIOS.keys())}"
            )
        params = _STRESS_SCENARIOS[scenario]
        dS_pct = params["dS_pct"]
        dvol_abs = params["dvol_abs"]
        dr_abs = params["dr_abs"]

        stressed_pnl = np.zeros(len(self.positions))
        for idx, pos in enumerate(self.positions):
            w = pos.quantity * pos.notional
            S_base = pos.K   # proxy for S
            sigma_base = 0.20
            r_base = self.r

            try:
                pricer_base = BSMPricer(
                    S=S_base, K=pos.K, T=max(pos.T, 1e-6),
                    r=r_base, sigma=sigma_base,
                    option_type=pos.option_type,
                )
                v_base = pricer_base.price()
            except Exception:
                v_base = 0.0

            S_s = max(S_base * (1.0 + dS_pct), 1e-6)
            sigma_s = max(sigma_base + dvol_abs, 1e-4)
            r_s = r_base + dr_abs

            try:
                pricer_s = BSMPricer(
                    S=S_s, K=pos.K, T=max(pos.T, 1e-6),
                    r=r_s, sigma=min(sigma_s, 5.0),
                    option_type=pos.option_type,
                )
                v_stressed = pricer_s.price()
            except Exception:
                v_stressed = 0.0

            stressed_pnl[idx] = w * (v_stressed - v_base)

        total_stressed_pnl = float(stressed_pnl.sum())
        var = float(max(-total_stressed_pnl, 0.0))
        cvar = var  # single scenario: VaR = CVaR

        return OptionsVaRResult(
            var=var,
            cvar=cvar,
            method="stress_scenario",
            confidence=1.0,
            horizon_days=1,
            n_scenarios=1,
            stressed_scenario=scenario,
        )
