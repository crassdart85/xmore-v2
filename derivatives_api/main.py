"""Xmore Derivatives Pricing API

FastAPI service wrapping the derivatives/ module.
Runs as a separate Render worker service; Express proxies to it.
"""
import os, sys, logging

# Ensure repo root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

from derivatives_api.schemas import (
    BSMRequest, BSMResponse,
    BinomialRequest, BinomialResponse,
    AsianRequest, MCResponse,
    BarrierRequest, HealthResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Xmore Derivatives API",
    description="Options pricing, Greeks, and risk for EGX/Tadawul instruments",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", version="1.0.0", derivatives_module="loaded")


# ---------------------------------------------------------------------------
# BSM
# ---------------------------------------------------------------------------

@app.post("/price/bsm", response_model=BSMResponse)
def price_bsm(request: BSMRequest):
    try:
        from derivatives.models.bsm import BSMPricer, ConvergenceError
        from derivatives.greeks.analytical import AnalyticalGreeks
        from derivatives.greeks.second_order import SecondOrderGreeksCalculator

        sigma_used = request.garch_vol if request.garch_vol is not None else request.sigma
        sigma_source = "garch" if request.garch_vol is not None else "manual"

        pricer = BSMPricer(
            S=request.S,
            K=request.K,
            T=request.T,
            r=request.r,
            sigma=request.sigma,
            option_type=request.option_type,
            q=request.q,
            garch_vol=request.garch_vol,
        )

        price = pricer.price()

        greeks = AnalyticalGreeks(pricer).compute()
        second = SecondOrderGreeksCalculator(pricer).compute()

        return BSMResponse(
            price=price,
            delta=greeks.delta,
            gamma=greeks.gamma,
            theta=greeks.theta,
            vega=greeks.vega,
            rho=greeks.rho,
            vanna=second.vanna,
            volga=second.volga,
            sigma_used=pricer.sigma,
            sigma_source=sigma_source,
            ticker=request.ticker,
        )

    except (ValueError, Exception) as exc:
        # Import ConvergenceError for isinstance check; re-raise as 422
        try:
            from derivatives.models.bsm import ConvergenceError
            if isinstance(exc, (ValueError, ConvergenceError)):
                raise HTTPException(status_code=422, detail=str(exc))
        except ImportError:
            pass
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc))
        logger.exception("BSM pricing error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Binomial
# ---------------------------------------------------------------------------

@app.post("/price/binomial", response_model=BinomialResponse)
def price_binomial(request: BinomialRequest):
    try:
        from derivatives.models.binomial import BinomialPricer

        pricer = BinomialPricer(
            S=request.S,
            K=request.K,
            T=request.T,
            r=request.r,
            sigma=request.sigma,
            option_type=request.option_type,
            q=request.q,
            n_steps=request.n_steps,
            american=request.american,
        )

        price = pricer.price()

        return BinomialResponse(
            price=price,
            american=request.american,
            n_steps=request.n_steps,
            ticker=request.ticker,
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Binomial pricing error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Synthetic SimulationResult helper
# ---------------------------------------------------------------------------

def _build_sim_result(S: float, r: float, sigma: float, q: float,
                      n_paths: int, n_steps: int, T: float, ticker: str):
    """Build a minimal SimulationResult-compatible object from GBM paths."""

    dt = T / n_steps
    rng = np.random.default_rng(42)

    # GBM: S_{t+1} = S_t * exp((r - q - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
    drift = (r - q - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt)
    Z = rng.standard_normal((n_paths, n_steps))
    log_returns = drift + diffusion * Z
    # Prepend log(S) at t=0, then cumsum for log prices, then exp
    log_paths = np.log(S) + np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(log_returns, axis=1)], axis=1
    )
    paths = np.exp(log_paths)  # shape (n_paths, n_steps+1)
    # Drop the initial column so shape is (n_paths, n_steps) matching MCDerivativesPricer
    paths = paths[:, 1:]

    class _SimResult:
        def __init__(self):
            self.paths = {ticker: paths}
            self.dt = dt

    return _SimResult()


# ---------------------------------------------------------------------------
# Asian
# ---------------------------------------------------------------------------

@app.post("/price/asian", response_model=MCResponse)
def price_asian(request: AsianRequest):
    try:
        from derivatives.models.mc_pricer import MCDerivativesPricer

        sim = _build_sim_result(
            S=request.S,
            r=request.r,
            sigma=request.sigma,
            q=request.q if hasattr(request, "q") else 0.0,
            n_paths=request.n_paths,
            n_steps=request.n_steps,
            T=request.T,
            ticker=request.ticker,
        )

        mc = MCDerivativesPricer(
            sim_result=sim,
            ticker=request.ticker,
            S0=request.S,
            r=request.r,
            q=getattr(request, "q", 0.0),
        )

        result = mc.price_asian(
            K=request.K,
            T=request.T,
            option_type=request.option_type,
            averaging=request.averaging,
        )

        return MCResponse(
            price=result["price"],
            std_err=result["std_err"],
            ci_low=result["ci_low"],
            ci_high=result["ci_high"],
            n_paths=result["n_paths"],
            ticker=request.ticker,
            product_type="asian",
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Asian pricing error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Barrier
# ---------------------------------------------------------------------------

@app.post("/price/barrier", response_model=MCResponse)
def price_barrier(request: BarrierRequest):
    try:
        from derivatives.models.mc_pricer import MCDerivativesPricer

        sim = _build_sim_result(
            S=request.S,
            r=request.r,
            sigma=request.sigma,
            q=getattr(request, "q", 0.0),
            n_paths=request.n_paths,
            n_steps=request.n_steps,
            T=request.T,
            ticker=request.ticker,
        )

        mc = MCDerivativesPricer(
            sim_result=sim,
            ticker=request.ticker,
            S0=request.S,
            r=request.r,
            q=getattr(request, "q", 0.0),
        )

        result = mc.price_barrier(
            K=request.K,
            T=request.T,
            barrier=request.barrier,
            barrier_type=request.barrier_type,
            option_type=request.option_type,
        )

        return MCResponse(
            price=result["price"],
            std_err=result["std_err"],
            ci_low=result["ci_low"],
            ci_high=result["ci_high"],
            n_paths=result["n_paths"],
            ticker=request.ticker,
            product_type=f"barrier_{request.barrier_type}",
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Barrier pricing error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Derivatives Brief
# ---------------------------------------------------------------------------

@app.get("/brief/{ticker}")
def derivatives_brief(
    ticker: str,
    S: float = Query(default=10.0, gt=0),
    K: float = Query(default=10.0, gt=0),
    T: float = Query(default=1.0, gt=0),
    r: float = Query(default=0.05),
    sigma: float = Query(default=0.20, gt=0, le=5.0),
    option_type: str = Query(default="call"),
):
    try:
        from derivatives.models.bsm import BSMPricer
        from derivatives.greeks.analytical import AnalyticalGreeks

        # BSM call
        call_pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="call")
        call_price = call_pricer.price()
        call_greeks = AnalyticalGreeks(call_pricer).compute()

        # BSM put
        put_pricer = BSMPricer(S=S, K=K, T=T, r=r, sigma=sigma, option_type="put")
        put_price = put_pricer.price()

        straddle = call_price + put_price
        straddle_pct = straddle / S * 100.0

        delta = call_greeks.delta
        delta_dollar = delta * S * 0.01  # 1% spot move
        theta = call_greeks.theta        # daily, in currency units
        vega = call_greeks.vega          # per 1% vol move

        narrative = (
            f"{ticker} \u2014 ATM call trades at EGP {call_price:.2f}, put at EGP {put_price:.2f}. "
            f"Straddle cost {straddle:.2f} ({straddle_pct:.1f}% of spot). "
            f"Delta {delta:.2f} \u2014 a 1% spot move gains/loses EGP {delta_dollar:.2f}. "
            f"Theta bleeds EGP {abs(theta):.2f}/day. Vol sensitivity EGP {vega:.2f} per 1% vol move."
        )

        return {
            "ticker": ticker,
            "narrative": narrative,
            "metrics": {
                "call_price": call_price,
                "put_price": put_price,
                "straddle": straddle,
                "straddle_pct": straddle_pct,
                "delta": delta,
                "delta_dollar": delta_dollar,
                "gamma": call_greeks.gamma,
                "theta": theta,
                "vega": vega,
                "rho": call_greeks.rho,
                "sigma_used": sigma,
                "S": S,
                "K": K,
                "T": T,
                "r": r,
            },
        }

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Brief error")
        raise HTTPException(status_code=500, detail=str(exc))
