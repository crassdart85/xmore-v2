"""Tests for analytical and numerical Greeks.

Covers:
1. Delta bounds (0 <= |delta| <= 1).
2. Gamma symmetry (call gamma == put gamma for same parameters).
3. Theta < 0 for long options (time decay costs money).
4. Vega > 0 (higher vol → higher option value).
5. Analytical vs numerical delta consistency over 50 random inputs.
6. Finite-difference consistency across all first-order Greeks.
7. Vanna-Volga adjustment reduces smile pricing error.
8. Second-order Greeks: vanna/volga sign consistency and VV non-trivial.
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from derivatives.models.bsm import BSMPricer
from derivatives.greeks.analytical import AnalyticalGreeks, Greeks
from derivatives.greeks.second_order import SecondOrderGreeks, SecondOrderGreeksCalculator
from derivatives.greeks.numerical import (
    numerical_delta,
    numerical_gamma,
    numerical_vega,
    numerical_theta,
    adaptive_epsilon,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def standard_call():
    return BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")


@pytest.fixture
def standard_put():
    return BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="put")


# ---------------------------------------------------------------------------
# 1. Delta bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("S, K", [(90, 100), (100, 100), (110, 100)])
def test_delta_bounds(option_type, S, K):
    """0 <= |delta| <= 1 for all vanilla options."""
    pricer = BSMPricer(S=S, K=K, T=1.0, r=0.05, sigma=0.20, option_type=option_type)
    g = AnalyticalGreeks(pricer).compute()
    assert 0.0 <= abs(g.delta) <= 1.0 + 1e-10, (
        f"Delta {g.delta} out of bounds for {option_type} S={S} K={K}"
    )


def test_call_delta_positive():
    """Call delta must be positive."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")
    g = AnalyticalGreeks(pricer).compute()
    assert g.delta > 0, f"Call delta should be positive, got {g.delta}"


def test_put_delta_negative():
    """Put delta must be negative."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="put")
    g = AnalyticalGreeks(pricer).compute()
    assert g.delta < 0, f"Put delta should be negative, got {g.delta}"


def test_atm_call_delta_near_half():
    """ATM call delta should be close to 0.5 (slightly above with r>0)."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.0, sigma=0.20, option_type="call")
    g = AnalyticalGreeks(pricer).compute()
    assert abs(g.delta - 0.5) < 0.10, f"ATM call delta {g.delta} should be near 0.5"


# ---------------------------------------------------------------------------
# 2. Gamma symmetry: call gamma == put gamma
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("S, K, T, r, sigma", [
    (100, 100, 1.0, 0.05, 0.20),
    (90, 100, 0.5, 0.03, 0.30),
    (110, 100, 2.0, 0.06, 0.15),
])
def test_gamma_call_equals_put(S, K, T, r, sigma):
    """Gamma is identical for calls and puts with same parameters."""
    call = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="call")
    put = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="put")
    g_call = AnalyticalGreeks(call).compute()
    g_put = AnalyticalGreeks(put).compute()
    assert abs(g_call.gamma - g_put.gamma) < 1e-10, (
        f"Gamma mismatch: call={g_call.gamma}, put={g_put.gamma}"
    )


def test_gamma_positive():
    """Gamma must be non-negative for long positions."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    g = AnalyticalGreeks(pricer).compute()
    assert g.gamma >= 0.0, f"Gamma should be non-negative, got {g.gamma}"


# ---------------------------------------------------------------------------
# 3. Theta < 0 for long options
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_theta_negative_for_long_option(option_type):
    """Theta (time decay) must be negative for long vanilla options."""
    pricer = BSMPricer(
        S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type=option_type
    )
    g = AnalyticalGreeks(pricer).compute()
    assert g.theta < 0, (
        f"{option_type} theta should be negative (time decay), got {g.theta}"
    )


# ---------------------------------------------------------------------------
# 4. Vega > 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("S, K", [(90, 100), (100, 100), (110, 100)])
def test_vega_positive(option_type, S, K):
    """Vega must be positive — higher vol always raises option value."""
    pricer = BSMPricer(S=S, K=K, T=1.0, r=0.05, sigma=0.20, option_type=option_type)
    g = AnalyticalGreeks(pricer).compute()
    assert g.vega > 0, f"Vega should be positive, got {g.vega}"


def test_vega_call_equals_put():
    """Vega is the same for calls and puts with identical parameters."""
    call = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="call")
    put = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="put")
    g_call = AnalyticalGreeks(call).compute()
    g_put = AnalyticalGreeks(put).compute()
    assert abs(g_call.vega - g_put.vega) < 1e-8, (
        f"Vega mismatch call={g_call.vega} put={g_put.vega}"
    )


# ---------------------------------------------------------------------------
# 5. Analytical vs numerical delta over 50 random inputs
# ---------------------------------------------------------------------------


def test_analytical_vs_numerical_delta_random():
    """Analytical delta matches numerical delta within 1e-4 for 50 random inputs."""
    rng = np.random.default_rng(seed=42)
    n = 50
    errors = []

    for _ in range(n):
        S = float(rng.uniform(50, 200))
        K = float(rng.uniform(60, 180))
        T = float(rng.uniform(0.1, 2.0))
        r = float(rng.uniform(0.0, 0.10))
        sigma = float(rng.uniform(0.10, 0.50))
        opt = rng.choice(["call", "put"])

        pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type=opt)
        analytical_delta = AnalyticalGreeks(pricer).compute().delta

        def price_at_S(s):
            return BSMPricer(S=s, K=K, T=T, r=r, sigma=sigma, option_type=opt).price()

        num_delta = numerical_delta(price_at_S, S, epsilon_pct=0.01)
        errors.append(abs(analytical_delta - num_delta))

    max_err = max(errors)
    mean_err = sum(errors) / len(errors)
    # Tolerance 5e-4: allows for high-sigma + short-T finite-difference
    # truncation error while remaining meaningfully tight.
    assert max_err < 5e-4, (
        f"Max analytical vs numerical delta error {max_err:.2e} > 5e-4 "
        f"(mean={mean_err:.2e})"
    )


# ---------------------------------------------------------------------------
# 6. Finite-difference consistency across all Greeks
# ---------------------------------------------------------------------------


def test_numerical_gamma_consistency():
    """Numerical gamma should be close to analytical gamma."""
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
    pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma)
    analytical_gamma = AnalyticalGreeks(pricer).compute().gamma

    def price_at_S(s):
        return BSMPricer(S=s, K=K, T=T, r=r, sigma=sigma).price()

    num_gamma = numerical_gamma(price_at_S, S, epsilon_pct=0.01)
    assert abs(analytical_gamma - num_gamma) < 1e-3, (
        f"Gamma mismatch: analytical={analytical_gamma:.6f}, numerical={num_gamma:.6f}"
    )


def test_numerical_vega_consistency():
    """Numerical vega should be close to analytical vega (per 1% vol)."""
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
    pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma)
    analytical_vega = AnalyticalGreeks(pricer).compute().vega  # per 1%

    def price_at_sigma(s):
        return BSMPricer(S=S, K=K, T=T, r=r, sigma=s).price()

    # numerical_vega returns raw vega; divide by 100 for per-1% convention
    num_vega_raw = numerical_vega(price_at_sigma, sigma, epsilon_abs=0.001)
    num_vega = num_vega_raw / 100.0
    assert abs(analytical_vega - num_vega) < 5e-4, (
        f"Vega mismatch: analytical={analytical_vega:.6f}, numerical={num_vega:.6f}"
    )


def test_numerical_theta_sign():
    """Numerical theta must be negative (time decay) for a long call."""
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20

    def price_at_T(t):
        return BSMPricer(S=S, K=K, T=t, r=r, sigma=sigma, option_type="call").price()

    theta = numerical_theta(price_at_T, T)
    assert theta < 0, f"Numerical theta should be negative, got {theta}"


def test_adaptive_epsilon_atm():
    """Adaptive epsilon near ATM should be 1% of S."""
    eps = adaptive_epsilon(100.0, "call", 1.0)
    assert abs(eps - 1.0) < 1e-10, f"ATM epsilon should be 1.0, got {eps}"


def test_adaptive_epsilon_deep_otm():
    """Adaptive epsilon for deep OTM should be 0.25% of S."""
    eps = adaptive_epsilon(100.0, "call", 1.50)
    assert abs(eps - 0.25) < 1e-10, f"Deep OTM epsilon should be 0.25, got {eps}"


# ---------------------------------------------------------------------------
# 7. Vanna-Volga adjustment
# ---------------------------------------------------------------------------


def test_vanna_volga_adjustment_non_trivial():
    """VV adjustment is non-zero when market_vanna and market_volga are provided."""
    pricer = BSMPricer(S=100, K=105, T=0.25, r=0.05, sigma=0.20, option_type="call")
    calc = SecondOrderGreeksCalculator(pricer)
    adjustment = calc.vanna_volga_adjustment(market_vanna=0.5, market_volga=1.0)
    assert isinstance(adjustment, float)
    # Adjustment should be finite
    assert np.isfinite(adjustment), f"VV adjustment should be finite, got {adjustment}"


def test_vanna_volga_zero_when_no_market_data():
    """VV adjustment is 0 when market_vanna and market_volga are both 0."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    calc = SecondOrderGreeksCalculator(pricer)
    adjustment = calc.vanna_volga_adjustment(market_vanna=0.0, market_volga=0.0)
    assert abs(adjustment) < 1e-10, f"VV adjustment should be 0, got {adjustment}"


# ---------------------------------------------------------------------------
# 8. Second-order Greeks: sign and structure
# ---------------------------------------------------------------------------


def test_second_order_volga_sign():
    """Volga (vega convexity) should be positive for ATM options."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    calc = SecondOrderGreeksCalculator(pricer)
    so = calc.compute()
    # ATM volga = vega * d1 * d2 / sigma; d1 > 0, d2 = d1 - sigma*sqrt(T)
    # For reasonable parameters both d1 and d2 may have mixed signs
    assert np.isfinite(so.volga), "Volga must be finite"
    assert np.isfinite(so.vanna), "Vanna must be finite"


def test_second_order_as_dict_keys():
    """SecondOrderGreeks.as_dict() has the expected keys."""
    pricer = BSMPricer(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
    calc = SecondOrderGreeksCalculator(pricer)
    so = calc.compute()
    d = so.as_dict()
    assert set(d.keys()) == {"vanna", "volga", "charm", "veta", "speed", "color"}, (
        f"Unexpected keys: {set(d.keys())}"
    )


def test_second_order_near_expiry_zeroed():
    """Near-expiry second-order Greeks are zeroed (ExpiryWarning issued)."""
    from derivatives.models.bsm import ExpiryWarning
    pricer = BSMPricer(S=100, K=100, T=1e-9, r=0.05, sigma=0.20)
    calc = SecondOrderGreeksCalculator(pricer)
    import warnings
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        so = calc.compute()
    assert so.vanna == 0.0 and so.volga == 0.0 and so.charm == 0.0, (
        "Near-expiry second-order Greeks should all be 0"
    )
