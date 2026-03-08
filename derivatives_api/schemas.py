from pydantic import BaseModel, Field
from typing import Optional, Literal


class BSMRequest(BaseModel):
    S: float = Field(..., gt=0, description="Spot price")
    K: float = Field(..., gt=0, description="Strike price")
    T: float = Field(..., gt=0, description="Time to expiry in years")
    r: float = Field(default=0.05, description="Risk-free rate")
    sigma: float = Field(..., gt=0, le=5.0, description="Volatility")
    option_type: Literal["call", "put"] = "call"
    q: float = Field(default=0.0, description="Dividend yield")
    garch_vol: Optional[float] = None
    ticker: str = Field(default="UNKNOWN")


class BSMResponse(BaseModel):
    price: float
    delta: float
    gamma: float
    theta: float   # daily
    vega: float    # per 1% vol
    rho: float     # per 1% rate
    vanna: float
    volga: float
    sigma_used: float
    sigma_source: str
    ticker: str


class BinomialRequest(BaseModel):
    S: float = Field(..., gt=0)
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0)
    r: float = 0.05
    sigma: float = Field(..., gt=0, le=5.0)
    option_type: Literal["call", "put"] = "call"
    q: float = 0.0
    n_steps: int = Field(default=200, ge=10, le=2000)
    american: bool = True
    ticker: str = "UNKNOWN"


class BinomialResponse(BaseModel):
    price: float
    american: bool
    n_steps: int
    ticker: str


class AsianRequest(BaseModel):
    ticker: str
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0)
    option_type: Literal["call", "put"] = "call"
    averaging: Literal["arithmetic", "geometric"] = "arithmetic"
    S: float = Field(..., gt=0)
    r: float = 0.05
    sigma: float = Field(..., gt=0, le=5.0)
    n_paths: int = Field(default=5000, ge=100, le=50000)
    n_steps: int = Field(default=252, ge=10, le=504)


class MCResponse(BaseModel):
    price: float
    std_err: float
    ci_low: float
    ci_high: float
    n_paths: int
    ticker: str
    product_type: str


class BarrierRequest(BaseModel):
    ticker: str
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0)
    barrier: float = Field(..., gt=0)
    barrier_type: Literal["up-and-out", "up-and-in", "down-and-out", "down-and-in"]
    option_type: Literal["call", "put"] = "call"
    S: float = Field(..., gt=0)
    r: float = 0.05
    sigma: float = Field(..., gt=0, le=5.0)
    n_paths: int = Field(default=5000, ge=100, le=50000)
    n_steps: int = Field(default=252, ge=10, le=504)


class HealthResponse(BaseModel):
    status: str
    version: str
    derivatives_module: str
