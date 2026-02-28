"""
GARCH Volatility Engine — Phase 1
===================================
Replaces static per-asset σ in the Monte Carlo simulation with time-varying
conditional volatility estimated by GARCH(1,1), GJR-GARCH(1,1), or EGARCH(1,1).

Key design decisions
---------------------
- Returns scaled ×100 for arch numerical stability; all outputs converted to decimal.
- Model selection: AIC/BIC comparison across variants when use_auto_select=True.
- Correlation: estimated on standardised GARCH residuals (ε/σ), not raw returns,
  so heteroskedasticity does not inflate correlation estimates.
- Error distribution: Student-t by default (captures fat tails of EGX returns).
- Simulation: vectorised over paths and assets; only the time dimension is sequential
  (unavoidable due to GARCH recursion).

Dependencies
------------
    pip install arch statsmodels
"""

from __future__ import annotations

import json
import logging
import pickle
import warnings
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Optional deps ────────────────────────────────────────────────────────────

try:
    from arch import arch_model as _arch_model
    HAS_ARCH = True
except ImportError:                                 # pragma: no cover
    HAS_ARCH = False
    logger.warning("arch library not installed — GARCH fitting unavailable.")

try:
    from statsmodels.stats.diagnostic import acorr_ljungbox as _ljungbox
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class GARCHParams:
    """Serialisable parameter bundle for one fitted GARCH asset model."""

    symbol:        str
    model_type:    str          # "garch" | "gjr_garch" | "egarch" | "static"
    mean_model:    str          # "constant" | "ar1"
    error_dist:    str          # "normal" | "studentt" | "skewt"

    # GARCH parameters (all in decimal² / dimensionless)
    omega:         float        # variance intercept (decimal²)
    alpha:         float        # ARCH(1) coefficient
    beta:          float        # GARCH(1) coefficient
    gamma:         float        # GJR asymmetry (0 for plain GARCH/EGARCH)
    mu:            float        # conditional mean (decimal daily return)
    nu:            float        # Student-t degrees of freedom (≥2.5)
    lambda_:       float        # skewness for skewed-t; 0 otherwise

    # Current state
    sigma_t:       float        # one-step-ahead conditional vol (decimal)
    h_t:           float        # conditional variance = sigma_t² (decimal²)

    # Model quality
    persistence:   float        # α + β + 0.5γ  (<1 ↔ stationary)
    aic:           float
    bic:           float
    log_likelihood: float
    n_obs:         int
    fit_warnings:  List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GARCHParams":
        return cls(**d)


# ── Helper ───────────────────────────────────────────────────────────────────

def _get(series: pd.Series, *keys: str, default: float = 0.0) -> float:
    """Safe parameter extraction from arch res.params (handles version differences)."""
    for k in keys:
        if k in series.index:
            return float(series[k])
    return default


# ── Main class ───────────────────────────────────────────────────────────────

class GARCHEngine:
    """
    Fits univariate GARCH models per asset and exposes a vectorised
    multivariate path simulator that preserves cross-asset correlation.

    Workflow
    --------
    1.  engine = GARCHEngine(model_preference="gjr_garch")
    2.  engine.fit(returns_df)          # DataFrame of daily log-returns
    3.  paths = engine.simulate_garch_paths(n_paths=5000, horizon=252)
    4.  engine.to_pickle("garch_state.pkl")  # audit trail
    """

    SUPPORTED_MODELS = ("garch", "gjr_garch", "egarch")

    def __init__(
        self,
        model_preference: Literal["garch", "gjr_garch", "egarch"] = "gjr_garch",
        error_dist:        Literal["normal", "studentt", "skewt"]   = "studentt",
        use_auto_select:   bool = True,
        min_obs:           int  = 60,
        seed:              int  = 42,
    ) -> None:
        """
        Parameters
        ----------
        model_preference : GARCH variant to fit; overridden by AIC when auto_select=True.
        error_dist       : Innovation distribution.
        use_auto_select  : Try all supported models and pick by AIC.
        min_obs          : Minimum observations; fallback to static vol if fewer.
        seed             : RNG seed for reproducibility.
        """
        self.model_preference = model_preference
        self.error_dist       = error_dist
        self.use_auto_select  = use_auto_select
        self.min_obs          = min_obs
        self.seed             = seed
        self.rng              = np.random.default_rng(seed)

        self._fitted:      Dict[str, GARCHParams] = {}
        self._residuals:   Dict[str, np.ndarray]  = {}   # standardised residuals
        self._corr_matrix: Optional[np.ndarray]   = None
        self._symbols:     List[str]               = []

    # ── Public API ───────────────────────────────────────────────────────────

    def fit(self, returns: pd.DataFrame) -> Dict[str, GARCHParams]:
        """
        Fit GARCH models for every column in *returns*.

        Parameters
        ----------
        returns : DataFrame of daily log-returns, shape (T, n_assets).
                  Columns must be asset symbols; index should be DatetimeIndex.

        Returns
        -------
        Mapping symbol → GARCHParams.
        """
        self._symbols = list(returns.columns)
        std_resid_dict: Dict[str, np.ndarray] = {}

        for symbol in self._symbols:
            series = returns[symbol].dropna()

            if not HAS_ARCH or len(series) < self.min_obs:
                logger.warning(
                    "%s: %s — using static-vol fallback",
                    symbol,
                    "arch not installed" if not HAS_ARCH else f"only {len(series)} obs",
                )
                self._fitted[symbol]    = self._fallback_params(symbol, series)
                std_resid_dict[symbol]  = self._demean_standardise(series)
                continue

            params = self._fit_best(symbol, series)
            self._fitted[symbol]   = params
            std_resid_dict[symbol] = self._compute_std_residuals(series, params)

            logger.info(
                "%-12s -> %-10s | AIC %8.1f | persist %.4f | sigma_t %.5f%s",
                symbol, params.model_type, params.aic,
                params.persistence, params.sigma_t,
                " [WARN] " + "; ".join(params.fit_warnings) if params.fit_warnings else "",
            )

        self._residuals   = std_resid_dict
        self._corr_matrix = self._build_corr_from_residuals(std_resid_dict)
        return dict(self._fitted)

    def simulate_garch_paths(
        self,
        n_paths:            int,
        horizon:            int,
        correlation_matrix: Optional[np.ndarray] = None,
        regime_h0_scale:    Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Generate correlated multivariate GARCH return paths.

        Parameters
        ----------
        n_paths            : Number of Monte Carlo paths.
        horizon            : Simulation horizon in trading days.
        correlation_matrix : Override; uses residual-based correlation if None.
        regime_h0_scale    : (n_assets,) array of regime-based vol scaling factors.
                             Applied to the starting variance h_0 only.

        Returns
        -------
        np.ndarray, shape (n_paths, horizon, n_assets) — daily log-returns (decimal).
        """
        if not self._fitted:
            raise RuntimeError("Call fit() before simulate_garch_paths().")

        n_assets = len(self._symbols)
        corr = correlation_matrix if correlation_matrix is not None else self._corr_matrix
        L    = np.linalg.cholesky(corr)                     # lower-triangular

        params_list = [self._fitted[s] for s in self._symbols]

        # GARCH parameter vectors (n_assets,)
        mu_v    = np.array([p.mu    for p in params_list])
        omega_v = np.array([p.omega for p in params_list])
        alpha_v = np.array([p.alpha for p in params_list])
        beta_v  = np.array([p.beta  for p in params_list])
        gamma_v = np.array([p.gamma for p in params_list])
        nu_v    = np.array([p.nu    for p in params_list])
        h0_v    = np.array([p.h_t   for p in params_list])

        # Optionally rescale starting variance for regime initialisation
        if regime_h0_scale is not None:
            h0_v = h0_v * (regime_h0_scale ** 2)

        # Pre-draw all innovations: shape (n_paths, horizon, n_assets)
        Z_raw  = self._draw_innovations(n_paths, horizon, n_assets, nu_v, params_list)
        # Apply Cholesky to correlate: (n_paths, horizon, n_assets) @ (n_assets, n_assets)ᵀ
        Z_corr = Z_raw @ L.T

        # Allocate output
        ret_paths = np.empty((n_paths, horizon, n_assets), dtype=np.float64)
        h = np.tile(h0_v, (n_paths, 1))   # (n_paths, n_assets) — current variance

        # ── GARCH recursion (sequential over t) ──────────────────────────
        for t in range(horizon):
            sigma = np.sqrt(np.maximum(h, 1e-12))          # (n_paths, n_assets)
            z_t   = Z_corr[:, t, :]                         # (n_paths, n_assets)
            eps_t = sigma * z_t                             # scaled innovation

            ret_paths[:, t, :] = mu_v + eps_t

            leverage = (eps_t < 0.0).astype(np.float64)    # GJR indicator
            h = (
                omega_v
                + alpha_v * eps_t ** 2
                + gamma_v * leverage * eps_t ** 2
                + beta_v  * h
            )
            h = np.maximum(h, 1e-12)

        return ret_paths

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_current_volatilities(self) -> Dict[str, float]:
        """Return current conditional volatility σ_t per asset (decimal)."""
        return {s: p.sigma_t for s, p in self._fitted.items()}

    def get_params(self) -> Dict[str, GARCHParams]:
        return dict(self._fitted)

    def get_correlation_matrix(self) -> np.ndarray:
        """Residual-based correlation matrix, shape (n_assets, n_assets)."""
        if self._corr_matrix is None:
            raise RuntimeError("Call fit() first.")
        return self._corr_matrix.copy()

    def params_to_json(self) -> str:
        """Serialise all fitted parameters to JSON for audit logging."""
        return json.dumps({s: p.to_dict() for s, p in self._fitted.items()}, indent=2)

    def to_pickle(self, path: str) -> None:
        """Persist entire fitted engine for auditability / warm reload."""
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def from_pickle(cls, path: str) -> "GARCHEngine":
        with open(path, "rb") as f:
            return pickle.load(f)

    # ── Private: fitting ─────────────────────────────────────────────────────

    def _fit_best(self, symbol: str, series: pd.Series) -> GARCHParams:
        """Fit all requested variants and return the one with lowest AIC."""
        models_to_try = (
            list(self.SUPPORTED_MODELS) if self.use_auto_select
            else [self.model_preference]
        )
        candidates: List[GARCHParams] = []
        for mtype in models_to_try:
            try:
                p = self._fit_single(symbol, series, mtype)
                candidates.append(p)
            except Exception as exc:
                logger.debug("%s / %s failed: %s", symbol, mtype, exc)

        if not candidates:
            logger.error("%s: all GARCH models failed — falling back to static vol.", symbol)
            return self._fallback_params(symbol, series)

        return min(candidates, key=lambda p: p.aic)

    def _fit_single(
        self, symbol: str, series: pd.Series, model_type: str
    ) -> GARCHParams:
        """Fit one GARCH variant and extract parameters in decimal units."""
        # ── Mean model: AR(1) if returns are autocorrelated (Ljung-Box p<0.05) ──
        lb_pval      = self._ljungbox_pvalue(series, lags=10)
        use_ar       = lb_pval < 0.05
        mean_kw      = "AR"       if use_ar else "Constant"
        lags_kw      = 1          if use_ar else 0
        mean_label   = "ar1"      if use_ar else "constant"

        dist_map = {"normal": "normal", "studentt": "t", "skewt": "skewt"}
        dist     = dist_map.get(self.error_dist, "t")

        # arch model construction
        scale = series * 100        # work in percent for numerical stability

        if model_type == "garch":
            am = _arch_model(scale, mean=mean_kw, lags=lags_kw,
                             vol="Garch", p=1, q=1, dist=dist)
        elif model_type == "gjr_garch":
            am = _arch_model(scale, mean=mean_kw, lags=lags_kw,
                             vol="GARCH", p=1, o=1, q=1, dist=dist)
        elif model_type == "egarch":
            am = _arch_model(scale, mean=mean_kw, lags=lags_kw,
                             vol="EGARCH", p=1, q=1, dist=dist)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = am.fit(disp="off", show_warning=False)

        p = res.params   # pandas Series

        # ── Extract parameters ─────────────────────────────────────────────
        # Mean (percent → decimal)
        mu_pct  = _get(p, "mu", "Const", "const", "Mean", default=float(scale.mean()))
        mu_d    = mu_pct / 100.0

        # Variance equation (omega in pct² → decimal²)
        omega_pct2 = _get(p, "omega", default=1e-6)
        omega_d    = omega_pct2 / 10_000.0

        alpha = _get(p, "alpha[1]", default=0.05)
        beta  = _get(p, "beta[1]",  default=0.90)
        gamma = _get(p, "gamma[1]", default=0.0)   # GJR only

        # Error distribution parameters
        nu  = _get(p, "nu", "eta",    default=30.0)
        lam = _get(p, "lambda", "xi", default=0.0)
        nu  = max(nu, 2.5)   # ensure finite variance

        # Current conditional volatility (pct → decimal)
        sigma_t = float(res.conditional_volatility.iloc[-1]) / 100.0
        h_t     = sigma_t ** 2

        # Persistence
        if model_type == "gjr_garch":
            persistence = alpha + beta + 0.5 * gamma
        elif model_type == "egarch":
            persistence = abs(beta)   # log-variance AR component
        else:
            persistence = alpha + beta

        warnings_list: List[str] = []
        if persistence >= 1.0:
            warnings_list.append(f"Non-stationary: persistence={persistence:.4f} ≥ 1")

        return GARCHParams(
            symbol=symbol,
            model_type=model_type,
            mean_model=mean_label,
            error_dist=self.error_dist,
            omega=omega_d,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            mu=mu_d,
            nu=nu,
            lambda_=lam,
            sigma_t=sigma_t,
            h_t=h_t,
            persistence=persistence,
            aic=float(res.aic),
            bic=float(res.bic),
            log_likelihood=float(res.loglikelihood),
            n_obs=int(res.nobs),
            fit_warnings=warnings_list,
        )

    # ── Private: innovations and correlation ─────────────────────────────────

    def _draw_innovations(
        self,
        n_paths:     int,
        horizon:     int,
        n_assets:    int,
        nu_v:        np.ndarray,
        params_list: List[GARCHParams],
    ) -> np.ndarray:
        """
        Draw (n_paths, horizon, n_assets) standardised innovations.
        Uses each asset's fitted error distribution with unit variance.
        """
        Z = np.empty((n_paths, horizon, n_assets), dtype=np.float64)
        for i, p in enumerate(params_list):
            if p.error_dist == "normal" or p.model_type == "static":
                Z[:, :, i] = self.rng.standard_normal((n_paths, horizon))
            else:
                nu = float(max(nu_v[i], 2.5))
                raw = self.rng.standard_t(df=nu, size=(n_paths, horizon))
                # Standardise to unit variance: divide by √(ν/(ν−2))
                Z[:, :, i] = raw / np.sqrt(nu / (nu - 2.0))
        return Z

    def _compute_std_residuals(
        self, series: pd.Series, params: GARCHParams
    ) -> np.ndarray:
        """
        Refit the best model to extract standardised residuals ε_t/σ_t.
        Used for building the innovation-based correlation matrix.
        """
        if not HAS_ARCH or params.model_type == "static":
            return self._demean_standardise(series)
        try:
            scale    = series * 100
            dist_map = {"normal": "normal", "studentt": "t", "skewt": "skewt"}
            dist     = dist_map.get(params.error_dist, "t")
            use_ar   = params.mean_model == "ar1"
            mean_kw  = "AR" if use_ar else "Constant"
            lags_kw  = 1    if use_ar else 0

            vol_kw_map = {"garch": "Garch", "gjr_garch": "GARCH", "egarch": "EGARCH"}
            vol_kw = vol_kw_map.get(params.model_type, "Garch")
            o_kw   = 1 if params.model_type == "gjr_garch" else 0

            am  = _arch_model(scale, mean=mean_kw, lags=lags_kw,
                              vol=vol_kw, p=1, o=o_kw, q=1, dist=dist)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = am.fit(disp="off", show_warning=False)
            return res.std_resid.values
        except Exception:
            return self._demean_standardise(series)

    def _build_corr_from_residuals(
        self, std_resid_dict: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """
        Estimate correlation from standardised GARCH residuals.
        Aligns series to common length, removes rows with any NaN/Inf,
        and projects result to nearest PSD.
        """
        min_len = min(len(v) for v in std_resid_dict.values())
        mat  = np.column_stack([std_resid_dict[s][-min_len:] for s in self._symbols])

        # Drop rows containing non-finite values before computing correlation
        finite_rows = np.isfinite(mat).all(axis=1)
        mat = mat[finite_rows]

        if mat.shape[0] < 10 or mat.shape[1] < 2:
            return np.eye(len(self._symbols))

        corr = np.corrcoef(mat, rowvar=False)
        if corr.ndim < 2:
            return np.array([[1.0]])
        return self._nearest_psd(corr)

    # ── Static utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _ljungbox_pvalue(series: pd.Series, lags: int = 10) -> float:
        """Return Ljung-Box p-value; fallback 0.5 (neutral) if unavailable."""
        if HAS_STATSMODELS:
            try:
                result = _ljungbox(series.dropna(), lags=[lags], return_df=True)
                return float(result["lb_pvalue"].iloc[-1])
            except Exception:
                pass
        # Minimal manual Ljung-Box using scipy
        try:
            from scipy import stats as _st
            n = len(series)
            acf = [float(pd.Series(series.values).autocorr(lag=k)) for k in range(1, lags + 1)]
            Q   = n * (n + 2) * sum(rho ** 2 / (n - k) for k, rho in enumerate(acf, 1))
            return float(1.0 - _st.chi2.cdf(Q, df=lags))
        except Exception:
            return 0.5

    @staticmethod
    def _nearest_psd(A: np.ndarray) -> np.ndarray:
        """Higham nearest-PSD via eigenvalue clipping; re-normalise to correlation."""
        # Sanitise: replace any non-finite off-diagonal with 0
        A = np.where(np.isfinite(A), A, 0.0)
        np.fill_diagonal(A, 1.0)
        try:
            eigvals, eigvecs = np.linalg.eigh(A)
        except np.linalg.LinAlgError:
            # Last resort: return identity
            return np.eye(A.shape[0])
        eigvals = np.maximum(eigvals, 1e-8)
        A_psd   = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d       = np.sqrt(np.diag(A_psd))
        d[d < 1e-12] = 1.0
        return A_psd / np.outer(d, d)

    @staticmethod
    def _demean_standardise(series: pd.Series) -> np.ndarray:
        """Fallback: return (x - μ)/σ as standardised proxy for residuals."""
        s = series.dropna()
        std = s.std()
        return ((s - s.mean()) / max(std, 1e-12)).values

    @staticmethod
    def _fallback_params(symbol: str, series: pd.Series) -> GARCHParams:
        """Static-vol fallback when GARCH fitting is infeasible."""
        s   = series.dropna()
        sig = float(s.std()) if len(s) > 1 else 0.01
        mu  = float(s.mean())
        return GARCHParams(
            symbol=symbol, model_type="static", mean_model="constant",
            error_dist="normal",
            omega=sig ** 2 * (1 - 0.10 - 0.85),
            alpha=0.10, beta=0.85, gamma=0.0,
            mu=mu, nu=30.0, lambda_=0.0,
            sigma_t=sig, h_t=sig ** 2, persistence=0.95,
            aic=float("inf"), bic=float("inf"), log_likelihood=float("-inf"),
            n_obs=len(s),
            fit_warnings=["Fallback to static vol (arch unavailable or insufficient data)"],
        )


# ── Standalone smoke-test ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-8s %(message)s")

    rng   = np.random.default_rng(0)
    T, N  = 500, 3
    syms  = ["COMI.CA", "ESRS.CA", "TMGH.CA"]
    # Synthetic GARCH(1,1) returns
    rets  = pd.DataFrame(rng.standard_normal((T, N)) * 0.015, columns=syms)

    engine = GARCHEngine(model_preference="gjr_garch", use_auto_select=True)
    fitted = engine.fit(rets)

    print("\n=== Fitted Parameters ===")
    for sym, p in fitted.items():
        print(f"  {sym}: {p.model_type} | sigma_t={p.sigma_t:.5f} | "
              f"persist={p.persistence:.4f} | AIC={p.aic:.1f}")

    paths = engine.simulate_garch_paths(n_paths=100, horizon=22)
    print(f"\n  Paths shape: {paths.shape}  (expected 100, 22, {N})")
    print(f"  Mean daily return sample: {paths.mean():.5f}")
    print(f"  Mean daily vol sample:    {paths.std():.5f}")
