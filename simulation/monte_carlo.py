"""Monte Carlo simulation engine — GBM with GARCH/HMM support."""
# DERIVATIVES MODULE INTEGRATION
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class SimulationResult:
    """Container for Monte Carlo simulation output.

    Attributes:
        paths: Mapping of ticker to price path array of shape (n_paths, n_steps).
        tickers: List of ticker symbols simulated.
        n_paths: Number of simulation paths.
        n_steps: Number of time steps per path.
        dt: Time step size in years (e.g. 1/252 for daily).
        garch_vols: Mapping of ticker to conditional volatility array of shape
            (n_steps, n_paths). Populated by the GARCH layer; derivatives module
            reads this but never writes it.
    """

    paths: Dict[str, np.ndarray]          # {ticker: shape(n_paths, n_steps)}
    tickers: list
    n_paths: int
    n_steps: int
    dt: float                              # time step in years
    garch_vols: Dict[str, np.ndarray] = field(default_factory=dict)
    # Shape (n_steps, n_paths) per ticker — stores conditional vol at each step
    # Populated by existing GARCH layer; derivatives module reads this, never writes it
    # DERIVATIVES MODULE INTEGRATION


def get_current_garch_vol(
    ticker: str,
    sim_result: Optional[SimulationResult] = None,
) -> float:
    """Return the most recent GARCH conditional volatility for a ticker.

    Args:
        ticker: The stock ticker symbol.
        sim_result: Optional SimulationResult. When provided, the vol at t=0
            of that simulation is returned. When None, a default historical
            vol estimate is returned.

    Returns:
        Annualised GARCH conditional volatility as a decimal (e.g. 0.20 = 20%).

    Notes:
        Used by BSMPricer for GARCH-adjusted option pricing.
        # DERIVATIVES MODULE INTEGRATION
    """
    if sim_result is not None and ticker in sim_result.garch_vols:
        vols = sim_result.garch_vols[ticker]
        if vols.ndim == 2:
            return float(vols[0, 0])
        return float(vols[0])
    return 0.20  # fallback: 20% historical vol
