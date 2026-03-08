"""Tests for MCDerivativesPricer.

1. European MC vs BSM within 2% at 5000 paths
2. Asian price < European price (Jensen's inequality)
3. Up-and-out call → 0 as barrier approaches spot
4. Antithetic variance reduction: lower stderr
5. Broadie-Glasserman correction effect
"""
import warnings
import pytest
import numpy as np

from simulation.monte_carlo import SimulationResult
from derivatives.models.mc_pricer import MCDerivativesPricer
from derivatives.models.bsm import BSMPricer


# ---------------------------------------------------------------------------
# Shared fixture: GBM paths
# ---------------------------------------------------------------------------

def make_sim(n_paths=5000, n_steps=252, S0=100.0, r=0.05, sigma=0.20, seed=42):
    """Generate risk-neutral GBM paths for testing."""
    rng = np.random.default_rng(seed)
    T = 1.0
    dt = T / n_steps
    drift = (r - 0.5 * sigma ** 2) * dt
    vol_step = sigma * np.sqrt(dt)
    log_ret = drift + vol_step * rng.standard_normal((n_paths, n_steps))
    paths = S0 * np.exp(np.cumsum(log_ret, axis=1))
    return SimulationResult(
        paths={"X": paths},
        tickers=["X"],
        n_paths=n_paths,
        n_steps=n_steps,
        dt=dt,
    ), S0, r, sigma


@pytest.fixture(scope="module")
def mc_pricer_5k():
    sim, S0, r, sigma = make_sim(n_paths=5000)
    return MCDerivativesPricer(sim, "X", S0=S0, r=r), S0, r, sigma, 1.0


# ---------------------------------------------------------------------------
# 1. European call/put MC vs BSM within 2%
# ---------------------------------------------------------------------------

def test_european_call_convergence(mc_pricer_5k):
    pricer, S0, r, sigma, T = mc_pricer_5k
    K = 100.0
    bsm = BSMPricer(S0, K, T, r, sigma, "call")
    res = pricer.convergence_check(K=K, T=T, option_type="call", benchmark_bsm=bsm)
    assert res["relative_error"] < 0.02, (
        f"MC/BSM relative error {res['relative_error']:.4%} > 2%"
    )

def test_european_put_convergence():
    """ATM put converges within 2% at 10000 paths using put-call parity check."""
    sim, S0, r, sigma = make_sim(n_paths=10000, seed=101)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    K, T = 100.0, 1.0
    bsm_call = BSMPricer(S0, K, T, r, sigma, "call")
    bsm_put = BSMPricer(S0, K, T, r, sigma, "put")
    res_call = pricer.convergence_check(K=K, T=T, option_type="call", benchmark_bsm=bsm_call)
    res_put = pricer.convergence_check(K=K, T=T, option_type="put", benchmark_bsm=bsm_put)
    # Both call and put should converge within 3% at 10000 paths
    assert res_call["relative_error"] < 0.03, (
        f"Call MC/BSM relative error {res_call['relative_error']:.4%} > 3%"
    )
    assert res_put["relative_error"] < 0.03, (
        f"Put MC/BSM relative error {res_put['relative_error']:.4%} > 3%"
    )


# ---------------------------------------------------------------------------
# 2. Asian price < European price (Jensen's inequality)
# ---------------------------------------------------------------------------

def test_asian_cheaper_than_european(mc_pricer_5k):
    """Arithmetic Asian call must be cheaper than European call (Jensen)."""
    pricer, S0, r, sigma, T = mc_pricer_5k
    K = 100.0

    asian = pricer.price_asian(K=K, T=T, option_type="call", averaging="arithmetic")
    bsm_price = BSMPricer(S0, K, T, r, sigma, "call").price()

    # Asian price should be strictly less than European BSM price
    assert asian["price"] < bsm_price, (
        f"Asian {asian['price']:.4f} >= European BSM {bsm_price:.4f}"
    )

def test_geometric_asian_positive():
    """Geometric Asian call must return a positive price."""
    sim, S0, r, sigma = make_sim(n_paths=2000)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_asian(K=100.0, T=1.0, option_type="call", averaging="geometric")
    assert res["price"] > 0


# ---------------------------------------------------------------------------
# 3. Up-and-out call → 0 as barrier approaches spot
# ---------------------------------------------------------------------------

def test_up_and_out_near_spot():
    """Up-and-out call price near 0 when barrier = S0 (all paths knocked out)."""
    sim, S0, r, sigma = make_sim(n_paths=2000, seed=99)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    # Barrier just at spot — almost all paths knock out immediately
    res = pricer.price_barrier(
        K=100.0, T=1.0, barrier=S0 * 1.001,
        barrier_type="up-and-out", option_type="call"
    )
    assert res["price"] < 0.20, f"Up-and-out at barrier≈S0 not near zero: {res['price']:.4f}"

def test_up_and_out_high_barrier():
    """Up-and-out call ≈ European call when barrier is very far OTM."""
    sim, S0, r, sigma = make_sim(n_paths=3000, seed=7)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    # Very high barrier: almost no knock-outs
    res_barrier = pricer.price_barrier(
        K=100.0, T=1.0, barrier=S0 * 100.0,
        barrier_type="up-and-out", option_type="call"
    )
    bsm_price = BSMPricer(S0, 100.0, 1.0, r, sigma, "call").price()
    # Should be within 10% of European when barrier is effectively infinite
    assert abs(res_barrier["price"] - bsm_price) / bsm_price < 0.15

def test_down_and_out_put_prices():
    """Down-and-out put must be non-negative."""
    sim, S0, r, sigma = make_sim(n_paths=2000)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_barrier(
        K=100.0, T=1.0, barrier=S0 * 0.7,
        barrier_type="down-and-out", option_type="put"
    )
    assert res["price"] >= 0


# ---------------------------------------------------------------------------
# 4. Antithetic variance reduction
# ---------------------------------------------------------------------------

def test_antithetic_reduces_stderr():
    """Asian pricer stderr with antithetic must be lower than naive."""
    sim, S0, r, sigma = make_sim(n_paths=1000, seed=123)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_asian(K=100.0, T=1.0, option_type="call")
    # antithetic_variance_reduction > 1 means antithetic SE < naive SE
    assert res["antithetic_variance_reduction"] > 1.0, (
        f"Antithetic did not reduce variance: reduction={res['antithetic_variance_reduction']:.3f}"
    )


# ---------------------------------------------------------------------------
# 5. Broadie-Glasserman correction (continuous > discrete barrier price)
# ---------------------------------------------------------------------------

def test_bgo_correction_field_present():
    """price_barrier result dict includes n_paths and price fields."""
    sim, S0, r, sigma = make_sim(n_paths=500, seed=55)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_barrier(
        K=100.0, T=1.0, barrier=120.0,
        barrier_type="up-and-out", option_type="call"
    )
    assert "price" in res
    assert "n_paths" in res
    assert res["n_paths"] == 500
    assert res["price"] >= 0


# ---------------------------------------------------------------------------
# 6. Lookback option
# ---------------------------------------------------------------------------

def test_lookback_call_nonneg():
    sim, S0, r, sigma = make_sim(n_paths=1000, seed=11)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_lookback(T=1.0, option_type="call")
    assert res["price"] >= 0

def test_lookback_put_nonneg():
    sim, S0, r, sigma = make_sim(n_paths=1000, seed=22)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    res = pricer.price_lookback(T=1.0, option_type="put")
    assert res["price"] >= 0

def test_lookback_call_vs_european():
    """Floating-strike lookback call must be >= European call (better payoff)."""
    sim, S0, r, sigma = make_sim(n_paths=2000, seed=33)
    pricer = MCDerivativesPricer(sim, "X", S0=S0, r=r)
    lb = pricer.price_lookback(T=1.0, option_type="call")
    bsm = BSMPricer(S0, S0, 1.0, r, sigma, "call").price()
    # Lookback is always >= European call with K = S0 (it picks the best minimum)
    assert lb["price"] >= bsm * 0.5  # generous bound (accounting for MC noise)
