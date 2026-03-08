"""Analytical Greeks for BSM options.

All formulas are derived from the Garman-Kohlhagen (1983) extension of
Black-Scholes for continuous dividend yield q.

Conventions:
* Delta: ∂V/∂S — raw, dimensionless.
* Gamma: ∂²V/∂S² — per unit S.
* Theta: daily P&L decay = -(∂V/∂t) / 252.
* Vega: ∂V/∂σ scaled to per 1% change in vol (divide raw by 100).
* Rho: ∂V/∂r scaled to per 1% change in rate (divide raw by 100).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Dict

import numpy as np
from scipy.stats import norm

from derivatives.models.bsm import BSMPricer, ExpiryWarning


# ---------------------------------------------------------------------------
# Greeks dataclass
# ---------------------------------------------------------------------------


@dataclass
class Greeks:
    """Container for first-order option Greeks.

    Attributes:
        delta: ∂V/∂S (dimensionless).
        gamma: ∂²V/∂S² (per unit S).
        theta: Daily time decay in currency units (negative for long options).
        vega: P&L change per 1% vol move in currency units.
        rho: P&L change per 1% rate move in currency units.
    """

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    def as_dict(self) -> Dict[str, float]:
        """Return Greeks as a plain dictionary.

        Returns:
            Dict with keys delta, gamma, theta, vega, rho.
        """
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
        }


# ---------------------------------------------------------------------------
# AnalyticalGreeks
# ---------------------------------------------------------------------------


class AnalyticalGreeks:
    """Compute closed-form BSM/GK Greeks for a single option position.

    Args:
        pricer: A fully-configured ``BSMPricer`` instance.

    Notes:
        * When T is very small (< 1e-6) gamma and vega are clamped to
          ``np.inf`` and an ``ExpiryWarning`` is issued.
        * When |d2| > 4, delta is at a boundary (0 or ±1) reflecting
          deep-OTM / deep-ITM behaviour.
    """

    _NEAR_EXPIRY = 1e-6

    def __init__(self, pricer: BSMPricer):
        self.pricer = pricer

    # ------------------------------------------------------------------
    # Public: compute
    # ------------------------------------------------------------------

    def compute(self) -> Greeks:
        """Compute all first-order Greeks.

        Returns:
            A populated ``Greeks`` dataclass.

        Raises:
            ExpiryWarning: When T < 1e-6 (near-expiry numerical extremes).

        Audit:
            Recommended: log via ``DerivativesLogger.log_greeks()`` after
            this call.
        """
        p = self.pricer
        S, K, T, r, q, sigma = p.S, p.K, p.T, p.r, p.q, p.sigma
        opt = p.option_type

        near_expiry = T < self._NEAR_EXPIRY
        if near_expiry:
            warnings.warn(
                f"T={T} is very small (< {self._NEAR_EXPIRY}); "
                "Gamma and Vega are numerically extreme.",
                ExpiryWarning,
                stacklevel=2,
            )

        sqrt_T = np.sqrt(T) if not near_expiry else 1e-3
        d1 = p.d1()
        d2 = p.d2()

        # ---- Delta ----
        if opt == "call":
            delta = float(np.exp(-q * T) * norm.cdf(d1))
        else:
            delta = float(-np.exp(-q * T) * norm.cdf(-d1))

        # Boundary clamp for deep OTM/ITM
        if abs(d2) > 4:
            if opt == "call":
                delta = 1.0 if d1 > 0 else 0.0
            else:
                delta = -1.0 if d1 < 0 else 0.0

        # ---- Gamma (same for calls and puts) ----
        if near_expiry:
            gamma = float(np.inf)
        else:
            gamma = float(
                np.exp(-q * T) * norm.pdf(d1) / (S * sigma * sqrt_T)
            )

        # ---- Theta (daily) ----
        # dV/dt (per year), then divide by 252 for daily
        if near_expiry:
            theta_annual = 0.0
        else:
            common = -(S * np.exp(-q * T) * norm.pdf(d1) * sigma) / (2.0 * sqrt_T)
            if opt == "call":
                theta_annual = (
                    common
                    - r * K * np.exp(-r * T) * norm.cdf(d2)
                    + q * S * np.exp(-q * T) * norm.cdf(d1)
                )
            else:
                theta_annual = (
                    common
                    + r * K * np.exp(-r * T) * norm.cdf(-d2)
                    - q * S * np.exp(-q * T) * norm.cdf(-d1)
                )
        theta = float(theta_annual / 252.0)

        # ---- Vega (per 1% vol move) ----
        if near_expiry:
            vega = float(np.inf)
        else:
            vega_raw = float(S * np.exp(-q * T) * norm.pdf(d1) * sqrt_T)
            vega = vega_raw / 100.0   # per 1% change

        # ---- Rho (per 1% rate move) ----
        if opt == "call":
            rho_raw = float(K * T * np.exp(-r * T) * norm.cdf(d2))
        else:
            rho_raw = float(-K * T * np.exp(-r * T) * norm.cdf(-d2))
        rho = rho_raw / 100.0   # per 1% change

        return Greeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )
