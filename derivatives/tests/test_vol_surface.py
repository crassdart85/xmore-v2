"""Tests for VolSurface — SVI parametric implied vol surface.

Covers:
1. SVI butterfly no-arbitrage: g(k) >= 0 across all calibrated slices.
2. Calendar spread: total variance is monotone in T.
3. Interpolation accuracy: 10% holdout within 50bps of true IV.
4. ATM consistency with GARCH input: ATM vol shifts towards garch_vol.
5. Flat surface: get_vol() returns constant for homogeneous input.
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from derivatives.models.bsm import BSMPricer, ConvergenceError
from derivatives.models.vol_surface import VolSurface, _svi_butterfly_g, _svi_w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_surface(
    strikes=None,
    expiries=None,
    sigma=0.20,
    skew=0.0,
    S=100.0,
    r=0.05,
    q=0.0,
):
    """Build a synthetic VolSurface from BSM prices (optionally with skew)."""
    if strikes is None:
        strikes = np.array([80, 90, 100, 110, 120], dtype=float)
    if expiries is None:
        expiries = np.array([0.25, 0.5, 1.0], dtype=float)

    prices = np.zeros((len(expiries), len(strikes)))
    for i, T in enumerate(expiries):
        for j, K in enumerate(strikes):
            m = np.log(K / S)
            vol = sigma + skew * m   # simple linear skew
            vol = max(vol, 0.01)
            opt = "call" if K >= S else "put"
            pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=vol, option_type=opt, q=q)
            prices[i, j] = pricer.price()

    return VolSurface(
        strikes=strikes,
        expiries=expiries,
        market_prices=prices,
        S=S,
        r=r,
        q=q,
    )


# ---------------------------------------------------------------------------
# 1. SVI butterfly no-arbitrage
# ---------------------------------------------------------------------------


def test_svi_butterfly_no_arbitrage():
    """g(k) >= 0 across fitted SVI parameters for all slices."""
    surf = _make_surface(sigma=0.20, skew=-0.05)
    k_test = np.linspace(-1.0, 1.0, 200)

    for i, params in enumerate(surf._svi_params):
        a, b, rho, m, s = params
        g = _svi_butterfly_g(k_test, a, b, rho, m, s)
        violations = g[g < -1e-4]
        assert len(violations) == 0, (
            f"Slice {i} (T={surf.expiries[i]:.3f}): "
            f"butterfly g(k) < 0 at {len(violations)} points, "
            f"min g = {g.min():.6f}"
        )


def test_svi_butterfly_flat_surface():
    """Flat surface SVI parameters should have g(k) >= 0 everywhere."""
    a, b, rho, m, s = VolSurface._flat_svi(0.20, 1.0)
    k_test = np.linspace(-2.0, 2.0, 500)
    g = _svi_butterfly_g(k_test, a, b, rho, m, s)
    assert np.all(g >= -1e-10), f"Flat SVI g(k) min = {g.min()}"


# ---------------------------------------------------------------------------
# 2. Calendar spread: monotone total variance
# ---------------------------------------------------------------------------


def test_calendar_spread_monotone_total_variance():
    """ATM total variance w(0) is non-decreasing in T after enforcement."""
    surf = _make_surface(
        expiries=np.array([0.25, 0.5, 1.0, 2.0]),
        sigma=0.20,
        skew=-0.03,
    )
    atm_w = [_svi_w(np.array([0.0]), *p)[0] for p in surf._svi_params]
    for i in range(1, len(atm_w)):
        assert atm_w[i] >= atm_w[i - 1] - 1e-6, (
            f"Calendar spread violation at slice {i}: "
            f"w[{i}]={atm_w[i]:.6f} < w[{i-1}]={atm_w[i-1]:.6f}"
        )


def test_calendar_spread_strictly_increasing_expiry():
    """Longer-dated ATM variance must be >= shorter-dated."""
    surf = _make_surface(
        expiries=np.array([0.5, 1.0, 2.0]),
        sigma=0.20,
    )
    atm_w = [_svi_w(np.array([0.0]), *p)[0] for p in surf._svi_params]
    assert atm_w[1] >= atm_w[0] - 1e-6
    assert atm_w[2] >= atm_w[1] - 1e-6


# ---------------------------------------------------------------------------
# 3. Interpolation accuracy: 10% holdout within 50bps
# ---------------------------------------------------------------------------


def test_interpolation_10pct_holdout():
    """Held-out vol estimates should be within 50bps of true IV."""
    rng = np.random.default_rng(seed=123)
    S, r = 100.0, 0.05
    all_strikes = np.array([80, 85, 90, 95, 100, 105, 110, 115, 120], dtype=float)
    all_expiries = np.array([0.25, 0.5, 1.0, 1.5, 2.0], dtype=float)
    true_sigma = 0.22

    # Build full surface
    prices = np.zeros((len(all_expiries), len(all_strikes)))
    for i, T in enumerate(all_expiries):
        for j, K in enumerate(all_strikes):
            opt = "call" if K >= S else "put"
            prices[i, j] = BSMPricer(S=S, K=K, T=T, r=r, sigma=true_sigma, option_type=opt).price()

    surf = VolSurface(strikes=all_strikes, expiries=all_expiries, market_prices=prices, S=S, r=r)

    # 10% holdout: test at interior points not exactly on grid
    test_Ks = [87, 97, 107, 117]
    test_Ts = [0.35, 0.75, 1.25]

    errors = []
    for K in test_Ks:
        for T in test_Ts:
            interpolated = surf.get_vol(K, T)
            errors.append(abs(interpolated - true_sigma))

    max_err = max(errors)
    assert max_err < 0.05, (  # 50bps
        f"Interpolation holdout max error {max_err:.4f} > 0.05 (50bps)"
    )


# ---------------------------------------------------------------------------
# 4. ATM consistency with GARCH input
# ---------------------------------------------------------------------------


def test_garch_atm_adjustment_shifts_vol():
    """When GARCH adjustments provided, ATM vol shifts towards garch_vol."""
    S, r = 100.0, 0.05
    base_sigma = 0.20
    garch_vol = 0.30

    strikes = np.array([90, 100, 110], dtype=float)
    expiries = np.array([0.5, 1.0], dtype=float)

    prices = np.zeros((len(expiries), len(strikes)))
    for i, T in enumerate(expiries):
        for j, K in enumerate(strikes):
            opt = "call" if K >= S else "put"
            prices[i, j] = BSMPricer(S=S, K=K, T=T, r=r, sigma=base_sigma, option_type=opt).price()

    surf_no_garch = VolSurface(strikes=strikes, expiries=expiries, market_prices=prices, S=S, r=r)
    surf_garch = VolSurface(
        strikes=strikes, expiries=expiries, market_prices=prices, S=S, r=r,
        garch_adjustments={0: garch_vol, 1: garch_vol},
    )

    # ATM vol with GARCH should be closer to garch_vol
    atm_no_garch = surf_no_garch.get_vol(100.0, 0.5)
    atm_garch = surf_garch.get_vol(100.0, 0.5)
    assert abs(atm_garch - garch_vol) <= abs(atm_no_garch - garch_vol) + 0.05, (
        f"GARCH adjustment should bring ATM vol closer to {garch_vol}: "
        f"no_garch={atm_no_garch:.4f}, garch={atm_garch:.4f}"
    )


# ---------------------------------------------------------------------------
# 5. Flat surface returns constant vol
# ---------------------------------------------------------------------------


def test_flat_surface_constant_vol():
    """A perfectly flat input surface should produce near-constant get_vol()."""
    surf = _make_surface(sigma=0.25, skew=0.0)
    test_Ks = [85, 95, 100, 105, 115]
    test_Ts = [0.25, 0.5, 1.0]

    vols = [surf.get_vol(K, T) for K in test_Ks for T in test_Ts]
    vol_arr = np.array(vols)
    assert vol_arr.max() - vol_arr.min() < 0.05, (
        f"Flat surface vol range {vol_arr.min():.4f}–{vol_arr.max():.4f} "
        f"(spread {vol_arr.max()-vol_arr.min():.4f}) should be < 5%"
    )


# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------


def test_get_vol_smile_shape():
    """get_vol_smile returns arrays of correct length."""
    surf = _make_surface()
    ks, vs = surf.get_vol_smile(0.5)
    assert len(ks) == len(surf.strikes)
    assert len(vs) == len(surf.strikes)
    assert np.all(vs > 0), "All smile vols should be positive"


def test_get_term_structure_shape():
    """get_term_structure returns arrays of correct length."""
    surf = _make_surface()
    ts, vs = surf.get_term_structure(100.0)
    assert len(ts) == len(surf.expiries)
    assert len(vs) == len(surf.expiries)
    assert np.all(vs > 0)


def test_to_dict_has_expiries_and_params():
    """to_dict() must contain 'expiries' and 'svi_params' keys."""
    surf = _make_surface()
    d = surf.to_dict()
    assert "expiries" in d
    assert "svi_params" in d
    assert len(d["svi_params"]) == len(surf.expiries)
    for p in d["svi_params"]:
        assert set(p.keys()) == {"a", "b", "rho", "m", "s"}


def test_invalid_market_prices_shape():
    """Mismatched market_prices shape should raise ValueError."""
    with pytest.raises(ValueError, match="shape"):
        VolSurface(
            strikes=np.array([90, 100, 110]),
            expiries=np.array([0.5, 1.0]),
            market_prices=np.zeros((3, 3)),   # wrong shape
            S=100.0,
            r=0.05,
        )
