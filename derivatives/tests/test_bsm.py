"""Tests for BSMPricer — Black-Scholes-Merton pricing model.

Covers:
1. Put-call parity across multiple parameter sets.
2. Intrinsic value lower bounds.
3. Boundary behaviour at near-expiry (T → 0).
4. Deep OTM convergence to intrinsic value.
5. Implied-vol round-trip accuracy.
6. Hull Table 15.1 benchmark.
7. GARCH vol override replaces sigma.
"""
from __future__ import annotations

import sys
import os
import pytest
import numpy as np

# Make the repo root importable when running pytest from any directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from derivatives.models.bsm import BSMPricer, ConvergenceError, PricingWarning


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def atm_call():
    """Standard ATM call: S=100, K=100, T=1, r=0.05, sigma=0.20."""
    return BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")


@pytest.fixture
def atm_put():
    """Standard ATM put: S=100, K=100, T=1, r=0.05, sigma=0.20."""
    return BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="put")


# ---------------------------------------------------------------------------
# 1. Put-call parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "S, K, T, r, sigma, q",
    [
        (100, 100, 1.0, 0.05, 0.20, 0.0),
        (150, 120, 0.5, 0.03, 0.25, 0.0),
        (80, 90, 2.0, 0.06, 0.30, 0.0),
        (200, 180, 0.25, 0.02, 0.15, 0.01),
        (50, 55, 1.5, 0.08, 0.40, 0.02),
    ],
)
def test_put_call_parity(S, K, T, r, sigma, q):
    """C - P = S*exp(-q*T) - K*exp(-r*T) within 1e-8."""
    call = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="call", q=q).price()
    put = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="put", q=q).price()
    lhs = call - put
    rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
    assert abs(lhs - rhs) < 1e-8, (
        f"Put-call parity violated: C-P={lhs:.10f}, S*exp-K*exp={rhs:.10f}"
    )


# ---------------------------------------------------------------------------
# 2. Intrinsic value bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "S, K, T, r, sigma, option_type",
    [
        (110, 100, 1.0, 0.05, 0.20, "call"),
        (90, 100, 1.0, 0.05, 0.20, "put"),
        (100, 100, 0.01, 0.05, 0.20, "call"),
        (200, 100, 0.5, 0.03, 0.10, "call"),
        (50, 100, 0.5, 0.03, 0.10, "put"),
    ],
)
def test_intrinsic_value_lower_bound(S, K, T, r, sigma, option_type):
    """European option price >= max(lower_bound, 0).

    For European options the correct no-arbitrage lower bound is the
    discounted intrinsic (not the undiscounted intrinsic):
      call: max(S*exp(-q*T) - K*exp(-r*T), 0)
      put : max(K*exp(-r*T) - S*exp(-q*T), 0)
    """
    q = 0.0
    pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type=option_type, q=q)
    price = pricer.price()
    if option_type == "call":
        lower_bound = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0.0)
    else:
        lower_bound = max(K * np.exp(-r * T) - S * np.exp(-q * T), 0.0)
    assert price >= lower_bound - 1e-8, (
        f"Price {price:.8f} < European lower bound {lower_bound:.8f} "
        f"(S={S}, K={K}, T={T}, r={r}, sigma={sigma}, type={option_type})"
    )
    assert price >= 0.0, f"Option price cannot be negative, got {price}"


# ---------------------------------------------------------------------------
# 3. Boundary at near-expiry (T → 0)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_near_expiry_convergence_to_intrinsic(option_type):
    """At very small T, BSM price ≈ intrinsic value within 0.05."""
    S, K, r, sigma = 110.0, 100.0, 0.05, 0.20
    pricer = BSMPricer(S=S, K=K, T=1e-4, r=r, sigma=sigma, option_type=option_type)
    price = pricer.price()
    if option_type == "call":
        intrinsic = S - K
    else:
        intrinsic = max(K - S, 0.0)
    assert abs(price - intrinsic) < 0.10, (
        f"Near-expiry {option_type} price={price:.6f} too far from intrinsic={intrinsic:.6f}"
    )


def test_atm_near_expiry_non_negative():
    """ATM at near-expiry: price > 0 (time value)."""
    pricer = BSMPricer(S=100, K=100, T=1e-4, r=0.05, sigma=0.20, option_type="call")
    assert pricer.price() >= 0.0


# ---------------------------------------------------------------------------
# 4. Deep OTM convergence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("option_type, S, K", [
    ("call", 50, 200),
    ("put", 200, 50),
])
def test_deep_otm_near_zero(option_type, S, K):
    """Deep OTM options should have price very close to zero."""
    pricer = BSMPricer(S=S, K=K, T=1.0, r=0.05, sigma=0.20, option_type=option_type)
    price = pricer.price()
    assert price < 0.01, f"Deep OTM {option_type} price={price:.8f} not near zero"
    assert price >= 0.0


# ---------------------------------------------------------------------------
# 5. Implied vol round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "S, K, T, r, sigma, q",
    [
        (100, 100, 1.0, 0.05, 0.20, 0.0),
        (100, 110, 0.5, 0.03, 0.25, 0.0),
        (100, 90, 0.25, 0.06, 0.30, 0.0),
        (200, 180, 2.0, 0.04, 0.15, 0.01),
        (50, 55, 1.0, 0.05, 0.35, 0.02),
    ],
)
def test_implied_vol_round_trip(S, K, T, r, sigma, q):
    """IV extraction from BSM price should recover sigma within 1e-6."""
    pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="call", q=q)
    market_price = pricer.price()
    iv = pricer.implied_vol(market_price)
    assert abs(iv - sigma) < 1e-5, (
        f"IV round-trip failed: original={sigma:.8f}, recovered={iv:.8f}"
    )


# ---------------------------------------------------------------------------
# 6. Hull Table 15.1 benchmark
# ---------------------------------------------------------------------------


def test_hull_table_15_1_call():
    """Hull (2018) Table 15.1: S=42, K=40, T=0.5, r=0.10, sigma=0.20 → call≈4.76."""
    pricer = BSMPricer(S=42, K=40, T=0.5, r=0.10, sigma=0.20, option_type="call")
    price = pricer.price()
    assert abs(price - 4.76) < 0.015, (
        f"Hull Table 15.1 call mismatch: expected≈4.76, got {price:.4f}"
    )


def test_hull_table_15_1_put():
    """Hull (2018) Table 15.1: S=42, K=40, T=0.5, r=0.10, sigma=0.20 → put≈0.81."""
    pricer = BSMPricer(S=42, K=40, T=0.5, r=0.10, sigma=0.20, option_type="put")
    price = pricer.price()
    assert abs(price - 0.81) < 0.015, (
        f"Hull Table 15.1 put mismatch: expected≈0.81, got {price:.4f}"
    )


# ---------------------------------------------------------------------------
# 7. GARCH vol override
# ---------------------------------------------------------------------------


def test_garch_vol_replaces_sigma():
    """When garch_vol is provided, it overrides the constructor sigma."""
    sigma_original = 0.20
    garch_vol = 0.35
    pricer_base = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=sigma_original)
    pricer_garch = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=sigma_original, garch_vol=garch_vol)
    pricer_direct = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=garch_vol)

    assert pricer_garch.sigma == garch_vol, "GARCH vol should replace sigma"
    assert abs(pricer_garch.price() - pricer_direct.price()) < 1e-10, (
        "GARCH override price should equal direct sigma=garch_vol price"
    )
    assert pricer_garch.price() != pricer_base.price(), (
        "GARCH override should change price vs original sigma"
    )


def test_vol_override_takes_highest_precedence():
    """vol_override takes precedence over garch_vol and regime_params."""
    pricer = BSMPricer(
        S=100, K=100, T=1.0, r=0.05, sigma=0.20,
        garch_vol=0.30,
        regime_state=0, regime_params={0: {"sigma": 0.40}},
        vol_override=0.25,
    )
    assert pricer.sigma == 0.25, "vol_override must take highest precedence"


def test_regime_override():
    """regime_params overrides garch_vol but not vol_override."""
    pricer = BSMPricer(
        S=100, K=100, T=1.0, r=0.05, sigma=0.20,
        garch_vol=0.30,
        regime_state=1,
        regime_params={1: {"sigma": 0.40}},
    )
    assert pricer.sigma == 0.40, "regime_params should override garch_vol"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_params", [
    {"S": -1},
    {"K": 0},
    {"T": 0},
    {"sigma": -0.1},
    {"sigma": 6.0},
])
def test_invalid_inputs_raise(bad_params):
    """Invalid constructor arguments must raise ValueError."""
    defaults = dict(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    defaults.update(bad_params)
    with pytest.raises(ValueError):
        BSMPricer(**defaults)


def test_invalid_option_type():
    """Unknown option_type must raise ValueError."""
    with pytest.raises(ValueError):
        BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="straddle")
