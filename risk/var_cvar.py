"""Portfolio VaR/CVaR — parametric, historical, and Monte Carlo methods.

This module provides ``PortfolioVaR``, a flexible class that computes
Value-at-Risk and Conditional Value-at-Risk (Expected Shortfall) from a
matrix of scenario returns.  It is deliberately free of external
dependencies beyond NumPy so that it can be used both in the main risk
pipeline and by ``derivatives/portfolio/var_integration.py``.
"""
# DERIVATIVES MODULE INTEGRATION
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class VaRResult:
    """Result container for a VaR/CVaR calculation.

    Attributes:
        var: Value-at-Risk expressed as a *positive* loss fraction
            (e.g. 0.05 means 5 % of portfolio value).
        cvar: Conditional VaR (Expected Shortfall), also positive.
        confidence: Confidence level (e.g. 0.99).
        horizon_days: Holding period in calendar days.
        method: One of ``"historical"``, ``"parametric"``, ``"monte_carlo"``.
        n_scenarios: Number of scenarios used in the calculation.
    """

    var: float
    cvar: float
    confidence: float
    horizon_days: int
    method: str
    n_scenarios: int


class PortfolioVaR:
    """Compute portfolio VaR/CVaR from a scenario return matrix.

    Args:
        returns: Scenario return matrix.  Acceptable shapes:

            * ``(n_scenarios,)`` — pre-computed portfolio returns.
            * ``(n_scenarios, n_assets)`` — per-asset returns; weights are
              applied internally.

        weights: Asset weights of shape ``(n_assets,)``.  Defaults to equal
            weighting when *returns* has more than one column.
    """

    def __init__(
        self,
        returns: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ):
        self.returns = (
            np.atleast_2d(returns) if returns.ndim == 1 else np.asarray(returns)
        )
        if weights is None and self.returns.ndim == 2:
            n = self.returns.shape[1]
            self.weights = np.ones(n) / n
        else:
            self.weights = weights if weights is not None else np.array([1.0])
        self._pnl: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _portfolio_pnl(self) -> np.ndarray:
        """Compute the portfolio-level P&L array (n_scenarios,)."""
        if self._pnl is None:
            if self.returns.ndim == 2 and self.returns.shape[1] > 1:
                self._pnl = self.returns @ self.weights
            else:
                self._pnl = self.returns.ravel()
        return self._pnl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        confidence: float = 0.99,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute historical-simulation VaR and CVaR.

        Args:
            confidence: Confidence level; must be in ``(0, 1)``.
            horizon_days: Holding period.  The square-root-of-time rule is
                applied to scale daily volatility.

        Returns:
            A ``VaRResult`` instance.
        """
        pnl = self._portfolio_pnl() * np.sqrt(horizon_days)
        var = float(-np.percentile(pnl, (1 - confidence) * 100))
        tail_mask = pnl <= -var
        cvar = float(-pnl[tail_mask].mean()) if tail_mask.any() else var
        return VaRResult(
            var=var,
            cvar=cvar,
            confidence=confidence,
            horizon_days=horizon_days,
            method="historical",
            n_scenarios=int(len(pnl)),
        )

    def get_scenario_pnl_distribution(self) -> np.ndarray:
        """Expose the simulated P&L distribution for downstream use.

        Returns the raw scenario P&L array *before* VaR/CVaR percentile
        extraction.  Shape is ``(n_scenarios,)``.

        Used by ``derivatives/portfolio/var_integration.py``
        ``OptionsVaR`` to apply option-specific shocks on top of the
        underlying P&L distribution.

        Returns:
            Copy of the scenario P&L array.

        # DERIVATIVES MODULE INTEGRATION
        """
        return self._portfolio_pnl().copy()
