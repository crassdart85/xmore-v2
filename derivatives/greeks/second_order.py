"""Second-order and cross Greeks for BSM options.

Implements the following higher-order sensitivities:
* Vanna  — ∂²V/∂S∂σ  = ∂delta/∂σ  = ∂vega/∂S
* Volga  — ∂²V/∂σ²   (also known as Vomma or Vega convexity)
* Charm  — ∂²V/∂S∂t  = ∂delta/∂t  (daily delta bleed)
* Veta   — ∂²V/∂σ∂t  = ∂vega/∂t   (daily vega bleed)
* Speed  — ∂³V/∂S³   (∂gamma/∂S)
* Color  — ∂³V/∂S²∂t (∂gamma/∂t, daily)

All formulas assume the GK (Garman-Kohlhagen) framework with continuous
dividend yield q.

Notes:
    The vanna-volga (VV) pricing adjustment computes the additional premium
    required to replicate the smile P&L for positions that are short vanna
    and volga relative to the market.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from derivatives.models.bsm import BSMPricer, ExpiryWarning


@dataclass
class SecondOrderGreeks:
    """Container for second-order and cross Greeks.

    Attributes:
        vanna: ∂²V/∂S∂σ — sensitivity of delta to vol changes.
        volga: ∂²V/∂σ²  — sensitivity of vega to vol changes (Vomma).
        charm: Daily ∂delta/∂t — daily delta bleed.
        veta: Daily ∂vega/∂t — daily vega bleed.
        speed: ∂³V/∂S³ — rate of change of gamma with spot.
        color: Daily ∂²V/∂S²∂t — daily gamma bleed.
    """

    vanna: float
    volga: float
    charm: float
    veta: float
    speed: float
    color: float

    def as_dict(self) -> dict:
        """Serialise to a plain dictionary.

        Returns:
            Dict with all six second-order Greek values.
        """
        return {
            "vanna": self.vanna,
            "volga": self.volga,
            "charm": self.charm,
            "veta": self.veta,
            "speed": self.speed,
            "color": self.color,
        }


class SecondOrderGreeksCalculator:
    """Compute second-order Greeks from a BSMPricer instance.

    Args:
        pricer: Fully configured ``BSMPricer``.

    Notes:
        Near-expiry (T < 1e-6) returns zeroed-out greeks with a warning.
    """

    _NEAR_EXPIRY = 1e-6

    def __init__(self, pricer: BSMPricer):
        self.pricer = pricer

    def compute(self) -> SecondOrderGreeks:
        """Compute all second-order Greeks.

        Returns:
            Populated ``SecondOrderGreeks`` dataclass.

        Raises:
            ExpiryWarning: When T < 1e-6.

        Notes:
            * charm and color are scaled to daily (divide annual by 252).
            * veta is expressed per 1% vol change per calendar day.
        """
        p = self.pricer
        S, K, T, r, q, sigma = p.S, p.K, p.T, p.r, p.q, p.sigma
        opt = p.option_type

        if T < self._NEAR_EXPIRY:
            warnings.warn(
                f"T={T} is near-zero; second-order Greeks clamped to 0.",
                ExpiryWarning,
                stacklevel=2,
            )
            return SecondOrderGreeks(
                vanna=0.0, volga=0.0, charm=0.0,
                veta=0.0, speed=0.0, color=0.0,
            )

        sqrt_T = np.sqrt(T)
        d1 = p.d1()
        d2 = p.d2()
        phi_d1 = norm.pdf(d1)
        N_d1 = norm.cdf(d1)
        N_neg_d1 = norm.cdf(-d1)
        N_d2 = norm.cdf(d2)
        N_neg_d2 = norm.cdf(-d2)
        exp_qT = np.exp(-q * T)
        exp_rT = np.exp(-r * T)

        # ---- Vanna: ∂²V/∂S∂σ = -(d2/σ) * phi(d1) * exp(-q*T) ----
        # Also equals vega / S - delta * d2/(sigma*sqrt_T) / 100
        # Using the direct formula:
        vanna = float(-exp_qT * phi_d1 * d2 / sigma)
        # Alternatively: vanna = (vega_raw / S) * (1 - d1 / (sigma * sqrt_T))
        # We use the clean form: -exp(-q*T) * N'(d1) * d2/sigma

        # ---- Volga (Vomma): ∂²V/∂σ² = vega_raw * d1 * d2 / sigma ----
        vega_raw = S * exp_qT * phi_d1 * sqrt_T
        volga = float(vega_raw * d1 * d2 / sigma)
        # Scale to per 1% (consistent with vega convention): divide by 100
        # (We keep raw here so vanna-volga adjustment works at the raw level)

        # ---- Charm: ∂delta/∂t (annual), then daily ----
        if opt == "call":
            charm_annual = float(
                q * exp_qT * N_d1
                - exp_qT * phi_d1 * (
                    2.0 * (r - q) * T - d2 * sigma * sqrt_T
                ) / (2.0 * T * sigma * sqrt_T)
            )
        else:
            charm_annual = float(
                -q * exp_qT * N_neg_d1
                - exp_qT * phi_d1 * (
                    2.0 * (r - q) * T - d2 * sigma * sqrt_T
                ) / (2.0 * T * sigma * sqrt_T)
            )
        charm = float(charm_annual / 252.0)

        # ---- Veta: ∂vega/∂t (annual), then daily/1% ----
        # ∂vega_raw/∂t = vega_raw * [ q - (r-q+σ²/2)/σ * d1/(2T) + (d1*d2)/(2T) ]
        # Using the standard formula:
        veta_annual = float(
            -S * exp_qT * phi_d1 * sqrt_T * (
                q
                + (r - q) * d1 / (sigma * sqrt_T)
                - (1.0 + d1 * d2) / (2.0 * T)
            )
        )
        veta = float(veta_annual / (252.0 * 100.0))  # daily, per 1%

        # ---- Speed: ∂gamma/∂S = -(d1/(S*sigma*sqrt_T) + 1/S) * gamma ----
        gamma = float(exp_qT * phi_d1 / (S * sigma * sqrt_T))
        speed = float(-gamma / S * (d1 / (sigma * sqrt_T) + 1.0))

        # ---- Color: ∂gamma/∂t (annual), then daily ----
        color_annual = float(
            -exp_qT * phi_d1 / (2.0 * S * T * sigma * sqrt_T) * (
                2.0 * q * T
                + 1.0
                + d1 * (2.0 * (r - q) * T - d2 * sigma * sqrt_T)
                / (sigma * sqrt_T)
            )
        )
        color = float(color_annual / 252.0)

        return SecondOrderGreeks(
            vanna=vanna,
            volga=volga,
            charm=charm,
            veta=veta,
            speed=speed,
            color=color,
        )

    def vanna_volga_adjustment(
        self,
        market_vanna: float,
        market_volga: float,
    ) -> float:
        """Compute the Vanna-Volga smile adjustment for this option.

        The VV method prices the vanna and volga risk of the option by
        hedging with three vanilla options (25Δ call, ATM, 25Δ put) traded
        at their market prices.  This implementation returns the *cost of
        hedging* vanna and volga risks as a single price adjustment.

        The simplified VV price adjustment is:

            ΔC_VV ≈ vega_raw × [ (market_vanna / vega_atm) × (d1×d2/σ) +
                                   (market_volga / vega_atm) × (d1×d2/σ)² ]

        In practice the adjustment reduces smile pricing error by matching
        the slope and curvature of the market smile.

        Args:
            market_vanna: Observed vanna of the reference 25Δ options
                (e.g. from liquid market quotes).
            market_volga: Observed volga of the reference ATM option.

        Returns:
            Adjustment to add to the BSM price (can be negative for OTM
            options with convex smile).

        Notes:
            * This is the Wystup (2003) simplified VV formula adapted for
              GK framework.
        """
        p = self.pricer
        S, K, T, r, q, sigma = p.S, p.K, p.T, p.r, p.q, p.sigma

        sqrt_T = np.sqrt(T)
        d1 = p.d1()
        d2 = p.d2()
        phi_d1 = norm.pdf(d1)
        exp_qT = np.exp(-q * T)

        vega_raw = S * exp_qT * phi_d1 * sqrt_T
        volga_raw = vega_raw * d1 * d2 / sigma

        # VV adjustment = 0.5 * (vanna_hedge_cost + volga_hedge_cost)
        if abs(market_vanna) < 1e-10 and abs(market_volga) < 1e-10:
            return 0.0

        vanna_term = 0.0
        volga_term = 0.0
        if abs(market_vanna) > 1e-12:
            vanna_term = float(self.compute().vanna / market_vanna * vega_raw * d2 / sigma)
        if abs(market_volga) > 1e-12:
            volga_term = float(volga_raw / market_volga * vega_raw * d1 * d2 / sigma)

        return float(0.5 * (vanna_term + volga_term))
