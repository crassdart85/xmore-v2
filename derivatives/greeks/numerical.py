"""Numerical (finite-difference) Greek approximations.

These standalone functions accept a *pricer callable* rather than a class
instance, making them model-agnostic.  They are primarily used for:

* Cross-checking analytical Greeks.
* Exotic model Greeks where analytical formulas do not exist.

All finite differences use central (2nd-order) schemes unless otherwise
noted.

Notes:
    The ``adaptive_epsilon`` helper selects an epsilon appropriate to the
    spot/vol/moneyness context to balance truncation error against round-off.
"""
from __future__ import annotations

from typing import Callable, Literal


# ---------------------------------------------------------------------------
# Adaptive epsilon
# ---------------------------------------------------------------------------


def adaptive_epsilon(
    S: float,
    option_type: str,
    moneyness: float,
) -> float:
    """Select an appropriate finite-difference epsilon for delta/gamma.

    The step size is scaled relative to the spot price and shrunk for
    deep-OTM options (where the payoff function is nearly flat) to reduce
    truncation error.

    Args:
        S: Current spot price.
        option_type: ``"call"`` or ``"put"``.
        moneyness: K/S ratio.

    Returns:
        Absolute epsilon for central finite-difference (in spot units).

    Notes:
        * Near ATM (0.95 <= K/S <= 1.05): 1% of S.
        * Deep OTM (K/S < 0.80 or K/S > 1.20): 0.25% of S.
        * Otherwise: 0.5% of S.
    """
    if 0.95 <= moneyness <= 1.05:
        frac = 0.01
    elif moneyness < 0.80 or moneyness > 1.20:
        frac = 0.0025
    else:
        frac = 0.005
    return max(frac * S, 1e-6)


# ---------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------


def numerical_delta(
    pricer_fn: Callable[[float], float],
    S: float,
    epsilon_pct: float = 0.01,
) -> float:
    """Compute numerical delta via central finite difference.

    Args:
        pricer_fn: Callable mapping spot price to option price.  Must accept
            a single float argument.
        S: Current spot price at which to evaluate delta.
        epsilon_pct: Step size as a fraction of S (default 1%).

    Returns:
        Numerical delta ≈ (V(S+ε) - V(S-ε)) / (2ε).

    Notes:
        Central difference gives O(ε²) accuracy.
    """
    eps = max(epsilon_pct * S, 1e-6)
    v_up = pricer_fn(S + eps)
    v_dn = pricer_fn(S - eps)
    return float((v_up - v_dn) / (2.0 * eps))


# ---------------------------------------------------------------------------
# Gamma
# ---------------------------------------------------------------------------


def numerical_gamma(
    pricer_fn: Callable[[float], float],
    S: float,
    epsilon_pct: float = 0.01,
) -> float:
    """Compute numerical gamma via second central finite difference.

    Args:
        pricer_fn: Callable mapping spot price to option price.
        S: Current spot price.
        epsilon_pct: Step size as a fraction of S (default 1%).

    Returns:
        Numerical gamma ≈ (V(S+ε) - 2V(S) + V(S-ε)) / ε².

    Notes:
        Uses the standard 3-point Laplacian stencil.
    """
    eps = max(epsilon_pct * S, 1e-6)
    v_up = pricer_fn(S + eps)
    v_mid = pricer_fn(S)
    v_dn = pricer_fn(S - eps)
    return float((v_up - 2.0 * v_mid + v_dn) / (eps ** 2))


# ---------------------------------------------------------------------------
# Vega
# ---------------------------------------------------------------------------


def numerical_vega(
    pricer_fn: Callable[[float], float],
    sigma: float,
    epsilon_abs: float = 0.001,
) -> float:
    """Compute numerical vega via central finite difference in vol.

    Args:
        pricer_fn: Callable mapping volatility (sigma) to option price.
        sigma: Current volatility at which to evaluate vega.
        epsilon_abs: Absolute step size in vol units (default 0.001 = 0.1%).

    Returns:
        Numerical vega (raw, per unit vol change).  Divide by 100 for
        per-1%-vol convention.

    Notes:
        * ``epsilon_abs`` defaults to 0.1% of vol, not 1% of spot.
        * The returned value is the *raw* vega; callers must scale
          to per-1% if needed.
    """
    eps = max(epsilon_abs, 1e-6)
    v_up = pricer_fn(sigma + eps)
    v_dn = pricer_fn(sigma - eps)
    return float((v_up - v_dn) / (2.0 * eps))


# ---------------------------------------------------------------------------
# Theta
# ---------------------------------------------------------------------------


def numerical_theta(
    pricer_fn: Callable[[float], float],
    T: float,
    epsilon_days: float = 1 / 252,
) -> float:
    """Compute numerical theta via backward finite difference in time.

    Uses a backward difference rather than central because option prices can
    lose continuity near expiry for very small T.

    Args:
        pricer_fn: Callable mapping time-to-expiry T (in years) to option
            price.
        T: Current time to expiry in years.
        epsilon_days: Step size in years (default 1/252 ≈ 1 trading day).

    Returns:
        Daily theta in currency units (typically negative for long options).

    Notes:
        * Returns the *daily* theta (already scaled by ``epsilon_days``).
        * For T <= epsilon_days a forward difference is used instead.
    """
    eps = float(epsilon_days)
    if T <= eps:
        # Forward difference: V(T) - V(T + eps) — price decreases as T shrinks
        v_now = pricer_fn(T)
        v_fwd = pricer_fn(max(T + eps, 1e-8))
        return float((v_now - v_fwd))   # already in daily units (eps = 1 day)
    else:
        v_now = pricer_fn(T)
        v_prev = pricer_fn(T - eps)
        # Theta = dV/dt; since T decreases with time, dV/dt = -dV/dT * dT/dt
        # dT/dt = -1, so theta_daily = -(V(T) - V(T-eps)) / eps * eps = V(T-eps) - V(T)
        return float(v_prev - v_now)   # already in daily units
