"""Portfolio-level Greek aggregation for multi-option books.

Aggregates first- and second-order Greeks across a list of ``OptionPosition``
objects, computes dollar Greeks, and generates delta-hedge ratios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from derivatives.greeks.analytical import Greeks
from derivatives.greeks.second_order import SecondOrderGreeks


# ---------------------------------------------------------------------------
# OptionPosition dataclass
# ---------------------------------------------------------------------------


@dataclass
class OptionPosition:
    """A single option position in the portfolio.

    Attributes:
        ticker: Underlying ticker symbol.
        option_type: ``"call"`` or ``"put"``.
        K: Strike price.
        T: Time to expiry in years.
        quantity: Number of contracts (negative = short).
        notional: Contract multiplier (e.g. 100 for standard equity options).
        greeks: First-order Greeks for a *single* contract.
        second_order: Optional second-order Greeks for a *single* contract.
    """

    ticker: str
    option_type: str
    K: float
    T: float
    quantity: float
    notional: float
    greeks: Greeks
    second_order: Optional[SecondOrderGreeks] = None


# ---------------------------------------------------------------------------
# PortfolioGreekSummary dataclass
# ---------------------------------------------------------------------------


@dataclass
class PortfolioGreekSummary:
    """Aggregated Greeks for the entire option book.

    Attributes:
        net_delta: Sum of quantity * notional * delta across all positions.
        net_gamma: Sum of quantity * notional * gamma.
        dollar_gamma: 0.5 * net_gamma * S² (P&L for a 1% spot move, squared).
            Here we store the per-position-weighted sum; caller should scale
            by S².
        net_vega: Sum of quantity * notional * vega (per 1% vol).
        net_theta: Sum of quantity * notional * theta (daily).
        net_vanna: Sum of quantity * notional * vanna (or 0 if unavailable).
        net_volga: Sum of quantity * notional * volga (or 0 if unavailable).
        moneyness_breakdown: Dict mapping moneyness bucket to net_delta.
            Buckets: ``"deep_itm"``, ``"itm"``, ``"atm"``, ``"otm"``, ``"deep_otm"``.
        delta_adjusted_exposure: Dict mapping ticker to dollar delta exposure.
    """

    net_delta: float
    net_gamma: float
    dollar_gamma: float
    net_vega: float
    net_theta: float
    net_vanna: float
    net_volga: float
    moneyness_breakdown: Dict[str, float]
    delta_adjusted_exposure: Dict[str, float]


# ---------------------------------------------------------------------------
# PortfolioGreeks
# ---------------------------------------------------------------------------


class PortfolioGreeks:
    """Aggregate Greeks for a book of option positions.

    Args:
        positions: List of ``OptionPosition`` objects.

    Notes:
        * Quantities must be signed (positive = long, negative = short).
        * ``notional`` is the contract multiplier, not the dollar notional.
    """

    # Moneyness bucket boundaries (K/S ratios)
    _BUCKETS = [
        ("deep_itm", 0.0, 0.85),
        ("itm", 0.85, 0.97),
        ("atm", 0.97, 1.03),
        ("otm", 1.03, 1.15),
        ("deep_otm", 1.15, float("inf")),
    ]

    def __init__(self, positions: List[OptionPosition]):
        self.positions = positions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _moneyness_bucket(K: float, S: float, option_type: str) -> str:
        """Classify an option into a moneyness bucket.

        Args:
            K: Strike price.
            S: Underlying spot price (inferred from position metadata; we
               use a proxy of K/delta but fall back to K/K=1.0 if S unknown).
            option_type: ``"call"`` or ``"put"``.

        Returns:
            Bucket label string.
        """
        ratio = K / S if S > 0 else 1.0
        # Adjust for puts: deep ITM put has high K/S
        if option_type == "put":
            ratio = 1.0 / ratio if ratio > 0 else 1.0
        for label, lo, hi in [
            ("deep_itm", 0.0, 0.85),
            ("itm", 0.85, 0.97),
            ("atm", 0.97, 1.03),
            ("otm", 1.03, 1.15),
            ("deep_otm", 1.15, float("inf")),
        ]:
            if lo <= ratio < hi:
                return label
        return "deep_otm"

    # ------------------------------------------------------------------
    # Public: aggregate
    # ------------------------------------------------------------------

    def aggregate(self) -> PortfolioGreekSummary:
        """Compute aggregate Greeks across all positions.

        Returns:
            A ``PortfolioGreekSummary`` with all fields populated.

        Notes:
            * ``dollar_gamma`` = 0.5 * net_gamma * (mean_S * 0.01)² captures
              the $ P&L for a 1% move in the underlying, averaged across
              tickers using their strike as a proxy for S.
            * Second-order Greeks are included only for positions that have
              ``second_order`` set; others contribute 0.

        Audit:
            Consider logging the summary dict via ``DerivativesLogger``.
        """
        net_delta = 0.0
        net_gamma = 0.0
        net_vega = 0.0
        net_theta = 0.0
        net_vanna = 0.0
        net_volga = 0.0
        moneyness: Dict[str, float] = {
            "deep_itm": 0.0, "itm": 0.0, "atm": 0.0, "otm": 0.0, "deep_otm": 0.0
        }
        ticker_delta: Dict[str, float] = {}

        sum_S_proxy = 0.0
        count = 0

        for pos in self.positions:
            w = pos.quantity * pos.notional
            g = pos.greeks

            net_delta += w * g.delta
            net_gamma += w * g.gamma
            net_vega += w * g.vega
            net_theta += w * g.theta

            if pos.second_order is not None:
                so = pos.second_order
                net_vanna += w * so.vanna
                net_volga += w * so.volga

            # Moneyness bucket (use K as proxy for S; gives rough bucket)
            # Ideally S would be stored in the position; use K as fallback
            S_proxy = pos.K / 1.0   # K itself as proxy when S unavailable
            # Use delta to back-infer rough moneyness
            abs_delta = abs(g.delta)
            if abs_delta >= 0.70:
                bucket = "deep_itm" if pos.option_type == "call" else "deep_otm"
            elif abs_delta >= 0.55:
                bucket = "itm" if pos.option_type == "call" else "otm"
            elif abs_delta >= 0.45:
                bucket = "atm"
            elif abs_delta >= 0.30:
                bucket = "otm" if pos.option_type == "call" else "itm"
            else:
                bucket = "deep_otm" if pos.option_type == "call" else "deep_itm"
            moneyness[bucket] = moneyness.get(bucket, 0.0) + w * g.delta

            # Ticker exposure
            ticker_delta[pos.ticker] = ticker_delta.get(pos.ticker, 0.0) + w * g.delta * pos.K

            sum_S_proxy += pos.K
            count += 1

        mean_S = sum_S_proxy / max(count, 1)
        dollar_gamma = float(0.5 * net_gamma * (mean_S * 0.01) ** 2)

        return PortfolioGreekSummary(
            net_delta=float(net_delta),
            net_gamma=float(net_gamma),
            dollar_gamma=float(dollar_gamma),
            net_vega=float(net_vega),
            net_theta=float(net_theta),
            net_vanna=float(net_vanna),
            net_volga=float(net_volga),
            moneyness_breakdown=moneyness,
            delta_adjusted_exposure=ticker_delta,
        )

    # ------------------------------------------------------------------
    # Public: delta_hedge_ratio
    # ------------------------------------------------------------------

    def delta_hedge_ratio(self, underlying_position: Dict[str, float]) -> Dict[str, float]:
        """Compute required delta-hedge trades per ticker.

        The hedge ratio is the number of underlying units needed to flatten
        the net delta of each ticker, given an existing underlying position.

        Args:
            underlying_position: Mapping of ticker to current underlying
                holding (signed units, e.g. ``{"COMI": 500}``).

        Returns:
            Mapping of ticker to required hedge trade (signed units).
            Positive = buy more underlying, negative = sell.

        Notes:
            * This is a *first-order* (delta-only) hedge.  Gamma re-hedging
              requires ``DeltaHedgeSimulator``.
        """
        # Net delta per ticker from all option positions
        ticker_net_delta: Dict[str, float] = {}
        for pos in self.positions:
            w = pos.quantity * pos.notional
            contrib = w * pos.greeks.delta
            ticker_net_delta[pos.ticker] = ticker_net_delta.get(pos.ticker, 0.0) + contrib

        hedge_trades: Dict[str, float] = {}
        for ticker, opt_delta in ticker_net_delta.items():
            current_underlying = underlying_position.get(ticker, 0.0)
            # To be delta-neutral: underlying_hold + opt_delta = 0
            hedge_trades[ticker] = float(-(opt_delta + current_underlying))

        return hedge_trades
