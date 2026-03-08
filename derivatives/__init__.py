"""Xmore derivatives module — options pricing, Greeks, vol surface, and risk.

Public API
----------
Pricing models:
    BSMPricer           — Black-Scholes-Merton (+ GARCH/regime/vol-surface hooks)
    BinomialPricer      — CRR binomial tree (American/European)
    MCDerivativesPricer — Monte Carlo pricer for exotics (Asian, Barrier, Lookback)
    VolSurface          — SVI parametric implied vol surface with no-arbitrage constraints

Greeks:
    AnalyticalGreeks    — Closed-form BSM/GK first-order Greeks
    Greeks              — First-order Greeks dataclass
    SecondOrderGreeks   — Dataclass for second-order / cross Greeks
    SecondOrderGreeksCalculator — Compute second-order Greeks from a BSMPricer
    numerical_delta, numerical_gamma, numerical_vega, numerical_theta
                        — Model-agnostic finite-difference Greeks
    adaptive_epsilon    — Adaptive step-size helper for numerical Greeks

Portfolio:
    OptionPosition      — Single-option position dataclass
    PortfolioGreeks     — Multi-position Greek aggregation + delta-hedge ratios
    PortfolioGreekSummary — Aggregated Greeks result dataclass
    DeltaHedgeSimulator — Monte Carlo delta-hedge simulation
    HedgeSimulationResult — Hedge simulation result dataclass
    OptionsVaR          — Options-aware VaR/CVaR (delta-gamma + full revaluation)
    OptionsVaRResult    — VaR result dataclass

Audit:
    DerivativesLogger   — SHA-256 hash-chained event logger for derivatives
    AuditFailureError   — Raised when chain integrity check fails

Exceptions / Warnings:
    ConvergenceError    — Newton-Raphson IV solver failed to converge
    PricingWarning      — Non-fatal numerical edge case during pricing
    ExpiryWarning       — T near zero; Greeks are numerically extreme
"""
from derivatives.models.bsm import BSMPricer, ConvergenceError, PricingWarning, ExpiryWarning
from derivatives.models.binomial import BinomialPricer
from derivatives.models.mc_pricer import MCDerivativesPricer
from derivatives.models.vol_surface import VolSurface
from derivatives.greeks.analytical import AnalyticalGreeks, Greeks
from derivatives.greeks.numerical import (
    numerical_delta,
    numerical_gamma,
    numerical_vega,
    numerical_theta,
    adaptive_epsilon,
)
from derivatives.greeks.second_order import SecondOrderGreeks, SecondOrderGreeksCalculator
from derivatives.portfolio.aggregator import PortfolioGreeks, OptionPosition, PortfolioGreekSummary
from derivatives.portfolio.hedge_simulator import DeltaHedgeSimulator, HedgeSimulationResult
from derivatives.portfolio.var_integration import OptionsVaR, OptionsVaRResult
from derivatives.audit.derivatives_logger import DerivativesLogger, AuditFailureError

__all__ = [
    # Models
    "BSMPricer",
    "BinomialPricer",
    "MCDerivativesPricer",
    "VolSurface",
    # Exceptions / warnings
    "ConvergenceError",
    "PricingWarning",
    "ExpiryWarning",
    "AuditFailureError",
    # Greeks
    "AnalyticalGreeks",
    "Greeks",
    "numerical_delta",
    "numerical_gamma",
    "numerical_vega",
    "numerical_theta",
    "adaptive_epsilon",
    "SecondOrderGreeks",
    "SecondOrderGreeksCalculator",
    # Portfolio
    "PortfolioGreeks",
    "OptionPosition",
    "PortfolioGreekSummary",
    "DeltaHedgeSimulator",
    "HedgeSimulationResult",
    "OptionsVaR",
    "OptionsVaRResult",
    # Audit
    "DerivativesLogger",
]
