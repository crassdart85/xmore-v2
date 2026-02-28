"""
Simulation Core — Unified Monte Carlo Engine
=============================================
Integrates GARCH volatility estimation (Phase 1) and HMM regime-switching
(Phase 2) behind a single backward-compatible simulate_paths() interface.

Usage
-----
    from engines.simulation_core import SimulationEngine, SimulationConfig

    config = SimulationConfig(
        volatility_model = "gjr_garch",   # "static" | "garch" | "gjr_garch" | "egarch"
        regime_model     = "hmm",         # "none" | "hmm"
        n_regimes        = 2,
        n_paths          = 5000,
        horizon          = 252,
        error_dist       = "studentt",
        seed             = 42,
    )

    engine = SimulationEngine(config)
    engine.fit(returns_df, index_returns=index_series)

    result = engine.simulate_paths()
    # result.return_paths  — (n_paths, horizon, n_assets)  daily log-returns
    # result.regime_paths  — (n_paths, horizon)             int regime labels (or None)
    # result.metadata      — audit dict logged on every call

Backward compatibility
----------------------
Callers that previously called simulate_paths(n_paths, horizon) on a legacy
engine can switch to SimulationConfig(volatility_model="static",
regime_model="none") to reproduce identical behaviour.

Performance target
------------------
5 000 paths × 252 days × 20 assets in < 10 s on a modern CPU.
GARCH fitting is done once at fit(); simulation is vectorised.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, NamedTuple, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Sub-module imports with graceful fallback ─────────────────────────────────

try:
    from engines.garch_engine import GARCHEngine, GARCHParams
    from engines.regime_model  import RegimeModel, RegimeState
except ImportError:
    try:
        from garch_engine import GARCHEngine, GARCHParams       # type: ignore
        from regime_model  import RegimeModel, RegimeState       # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Cannot locate garch_engine / regime_model. "
            "Ensure engines/ is on sys.path."
        ) from exc


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class SimulationConfig:
    """
    All knobs for a simulation run.  Pass to SimulationEngine constructor.

    Attributes
    ----------
    volatility_model  : "static"    — constant σ from historical returns
                        "garch"     — GARCH(1,1)
                        "gjr_garch" — GJR-GARCH(1,1)  [default / recommended]
                        "egarch"    — EGARCH(1,1)
    regime_model      : "none" — no regime switching
                        "hmm"  — Gaussian HMM on index features
    n_regimes         : 2 or 3 (used when regime_model="hmm").
    n_paths           : Monte Carlo path count.
    horizon           : Simulation horizon in trading days.
    error_dist        : Innovation distribution for GARCH.
    use_auto_select   : Auto-pick best GARCH variant and HMM K by AIC/BIC.
    seed              : Global RNG seed.  Stored in every simulation output.
    min_obs_for_garch : Minimum return observations for GARCH; fallback to
                        static vol otherwise.
    """

    volatility_model:  str  = "gjr_garch"
    regime_model:      str  = "hmm"
    n_regimes:         int  = 2
    n_paths:           int  = 5_000
    horizon:           int  = 252
    error_dist:        str  = "studentt"
    use_auto_select:   bool = True
    seed:              int  = 42
    min_obs_for_garch: int  = 60

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationConfig":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# ── Result container ──────────────────────────────────────────────────────────

class SimulationResult(NamedTuple):
    """Immutable result of one simulate_paths() call."""

    return_paths:  np.ndarray                 # (n_paths, horizon, n_assets) float64
    regime_paths:  Optional[np.ndarray]       # (n_paths, horizon) int32  or None
    symbols:       List[str]
    config:        SimulationConfig
    regime_state:  Optional[RegimeState]
    garch_params:  Optional[Dict[str, GARCHParams]]
    metadata:      dict                       # audit log


# ── Engine ────────────────────────────────────────────────────────────────────

class SimulationEngine:
    """
    Unified Monte Carlo engine.

    fit()            — fits GARCH and/or HMM according to config (once).
    simulate_paths() — generates paths; can be called many times after fit().
    """

    def __init__(self, config: Optional[SimulationConfig] = None) -> None:
        self.config = config or SimulationConfig()
        self.rng    = np.random.default_rng(self.config.seed)

        # Sub-engines
        self._garch:  Optional[GARCHEngine] = None
        self._regime: Optional[RegimeModel] = None

        # Static fallback parameters
        self._static_mu:   Optional[np.ndarray] = None
        self._static_sigma: Optional[np.ndarray] = None
        self._static_corr:  Optional[np.ndarray] = None

        self._symbols:    List[str] = []
        self._is_fitted:  bool      = False

    # ── Fitting ───────────────────────────────────────────────────────────────

    def fit(
        self,
        returns:        pd.DataFrame,
        index_returns:  Optional[pd.Series] = None,
    ) -> "SimulationEngine":
        """
        Fit all sub-models.

        Parameters
        ----------
        returns       : Daily log-returns, shape (T, n_assets).
                        Columns = asset symbols; DatetimeIndex recommended.
        index_returns : Market-index daily log-returns for HMM regime detection.
                        If None and regime_model="hmm", uses equal-weight
                        portfolio return as regime signal.

        Returns
        -------
        self  (enables method chaining)
        """
        self._symbols = list(returns.columns)

        # ── Static baseline (always; used as fallback) ────────────────────
        self._static_mu    = returns.mean().values.astype(np.float64)
        self._static_sigma = returns.std().values.astype(np.float64)
        raw_corr           = np.corrcoef(returns.T)
        if raw_corr.ndim < 2:
            raw_corr = np.array([[1.0]])
        self._static_corr  = _nearest_psd(raw_corr)

        # ── Phase 1: GARCH ────────────────────────────────────────────────
        if self.config.volatility_model != "static":
            self._garch = GARCHEngine(
                model_preference = self.config.volatility_model,
                error_dist       = self.config.error_dist,
                use_auto_select  = self.config.use_auto_select,
                min_obs          = self.config.min_obs_for_garch,
                seed             = self.config.seed,
            )
            self._garch.fit(returns)
            logger.info("GARCH fitting complete (%d assets).", len(self._symbols))

        # ── Phase 2: HMM ──────────────────────────────────────────────────
        if self.config.regime_model == "hmm":
            if index_returns is None:
                index_returns = returns.mean(axis=1)
                logger.info("No index_returns supplied — using equal-weight portfolio.")

            self._regime = RegimeModel(
                n_regimes       = self.config.n_regimes,
                use_auto_select = self.config.use_auto_select,
                seed            = self.config.seed,
            )
            self._regime.fit(index_returns)
            logger.info("HMM fitting complete.\n%s",
                        self._regime.get_regime_state().summary())

        self._is_fitted = True
        return self

    # ── Simulation (primary entry point) ──────────────────────────────────────

    def simulate_paths(
        self,
        n_paths: Optional[int] = None,
        horizon: Optional[int] = None,
    ) -> SimulationResult:
        """
        Generate Monte Carlo return paths.

        Parameters
        ----------
        n_paths : Override config.n_paths.
        horizon : Override config.horizon.

        Returns
        -------
        SimulationResult — see class docstring.
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before simulate_paths().")

        n_paths = n_paths or self.config.n_paths
        horizon = horizon or self.config.horizon

        t0             = time.perf_counter()
        regime_paths:  Optional[np.ndarray]              = None
        regime_state:  Optional[RegimeState]             = None
        garch_params:  Optional[Dict[str, GARCHParams]]  = None

        # ── Dispatch ──────────────────────────────────────────────────────
        use_garch  = self.config.volatility_model != "static"
        use_regime = self.config.regime_model == "hmm"

        if not use_garch and not use_regime:
            return_paths = self._sim_static(n_paths, horizon)

        elif use_garch and not use_regime:
            return_paths = self._sim_garch_only(n_paths, horizon)
            garch_params = self._garch.get_params()

        elif not use_garch and use_regime:
            return_paths, regime_paths = self._sim_static_hmm(n_paths, horizon)
            regime_state = self._regime.get_regime_state()

        else:   # GARCH + HMM
            return_paths, regime_paths = self._sim_garch_hmm(n_paths, horizon)
            garch_params = self._garch.get_params()
            regime_state = self._regime.get_regime_state()

        elapsed  = time.perf_counter() - t0
        metadata = self._build_audit(n_paths, horizon, elapsed,
                                     garch_params, regime_state)
        self._log_audit(metadata)

        return SimulationResult(
            return_paths = return_paths,
            regime_paths = regime_paths,
            symbols      = list(self._symbols),
            config       = self.config,
            regime_state = regime_state,
            garch_params = garch_params,
            metadata     = metadata,
        )

    # ── Simulation implementations ────────────────────────────────────────────

    def _sim_static(self, n_paths: int, horizon: int) -> np.ndarray:
        """
        Classic GBM Monte Carlo with static drift and volatility.
        Drift adjusted for Itô correction: μ_adj = μ − 0.5σ².
        """
        n_assets = len(self._symbols)
        L        = np.linalg.cholesky(self._static_corr)
        Z        = self.rng.standard_normal((n_paths, horizon, n_assets))
        Z_corr   = Z @ L.T
        mu_adj   = self._static_mu - 0.5 * self._static_sigma ** 2
        return mu_adj + Z_corr * self._static_sigma

    def _sim_garch_only(self, n_paths: int, horizon: int) -> np.ndarray:
        """GARCH paths, no regime switching."""
        return self._garch.simulate_garch_paths(n_paths=n_paths, horizon=horizon)

    def _sim_static_hmm(
        self, n_paths: int, horizon: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Static-vol paths with regime-conditioned volatility scaling.
        Fully vectorised — no time loop.
        """
        n_assets        = len(self._symbols)
        regime_paths    = self._regime.simulate_regime_paths(n_paths, horizon)
        regime_vols_ann = self._regime.get_regime_volatilities()          # (K,)
        regime_vols_day = regime_vols_ann / np.sqrt(252.0)                # (K,)

        # Portfolio-average daily vol as normalisation anchor
        avg_daily_sigma = float(self._static_sigma.mean())

        L      = np.linalg.cholesky(self._static_corr)
        Z      = self.rng.standard_normal((n_paths, horizon, n_assets))
        Z_corr = Z @ L.T                                                   # (n_paths, horizon, n_assets)

        # Map each (path, time) cell to regime daily vol: (n_paths, horizon)
        sigma_regime = regime_vols_day[regime_paths]

        # Per-asset vol scaling: regime_vol / avg_vol * asset_vol
        # Broadcast: (n_paths, horizon, 1) * (1, 1, n_assets)
        sigma_scaled = (
            (sigma_regime / avg_daily_sigma)[:, :, np.newaxis]
            * self._static_sigma[np.newaxis, np.newaxis, :]
        )   # (n_paths, horizon, n_assets)

        return_paths = self._static_mu + sigma_scaled * Z_corr
        return return_paths, regime_paths

    def _sim_garch_hmm(
        self, n_paths: int, horizon: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Full GARCH + HMM simulation.

        Strategy
        --------
        1. Simulate (n_paths, horizon) regime paths from HMM.
        2. Initialise each path's GARCH variance from its starting regime.
        3. At each time step, detect regime transitions and re-initialise h
           for paths that switched, then apply the standard GARCH recursion.

        The GARCH parameters (ω, α, β, γ) remain the same across regimes;
        only the initial h_t is regime-conditioned.  This is the
        "regime-conditional initialisation" approach, which is numerically
        stable and interpretable without requiring per-regime GARCH re-fits.
        """
        n_assets        = len(self._symbols)
        regime_paths    = self._regime.simulate_regime_paths(n_paths, horizon)
        regime_vols_ann = self._regime.get_regime_volatilities()           # (K,) annualised
        regime_vols_day = regime_vols_ann / np.sqrt(252.0)                # (K,)

        K = self.config.n_regimes

        # Cholesky of GARCH residual correlation
        corr = self._garch.get_correlation_matrix()
        L    = np.linalg.cholesky(corr)

        # GARCH parameter vectors (n_assets,)
        params_list = [self._garch.get_params()[s] for s in self._symbols]
        mu_v    = np.array([p.mu    for p in params_list])
        omega_v = np.array([p.omega for p in params_list])
        alpha_v = np.array([p.alpha for p in params_list])
        beta_v  = np.array([p.beta  for p in params_list])
        gamma_v = np.array([p.gamma for p in params_list])
        nu_v    = np.array([p.nu    for p in params_list])
        h0_v    = np.array([p.h_t   for p in params_list])     # (n_assets,)

        # Regime-specific starting variances (n_regimes, n_assets)
        # Clip to [0.2 × h0, 10 × h0] to prevent extreme re-initialisation
        regime_h = np.clip(
            (regime_vols_day[:, np.newaxis] ** 2)
            * np.ones((K, n_assets)),
            0.2 * h0_v,
            10.0 * h0_v,
        )   # (K, n_assets)

        # Pre-draw innovations: (n_paths, horizon, n_assets)
        Z_raw  = self._draw_garch_innovations(n_paths, horizon, n_assets,
                                              nu_v, params_list)
        Z_corr = Z_raw @ L.T

        # Initialise variance from each path's starting regime
        init_regimes = regime_paths[:, 0]              # (n_paths,)
        h = regime_h[init_regimes]                     # (n_paths, n_assets)

        ret_paths   = np.empty((n_paths, horizon, n_assets), dtype=np.float64)
        prev_regime = init_regimes.copy()

        for t in range(horizon):
            curr_regime = regime_paths[:, t]

            # Re-initialise h on regime transitions
            transitioned = (curr_regime != prev_regime)
            if transitioned.any():
                new_k                = curr_regime[transitioned]   # (m,)
                h[transitioned]      = regime_h[new_k]

            # GARCH step
            sigma   = np.sqrt(np.maximum(h, 1e-12))
            z_t     = Z_corr[:, t, :]
            eps_t   = sigma * z_t
            ret_paths[:, t, :] = mu_v + eps_t

            leverage = (eps_t < 0.0).astype(np.float64)
            h = (
                omega_v
                + alpha_v * eps_t ** 2
                + gamma_v * leverage * eps_t ** 2
                + beta_v  * h
            )
            h            = np.maximum(h, 1e-12)
            prev_regime  = curr_regime

        return ret_paths, regime_paths

    # ── Innovation drawing ────────────────────────────────────────────────────

    def _draw_garch_innovations(
        self,
        n_paths:     int,
        horizon:     int,
        n_assets:    int,
        nu_v:        np.ndarray,
        params_list: list,
    ) -> np.ndarray:
        Z = np.empty((n_paths, horizon, n_assets), dtype=np.float64)
        for i, p in enumerate(params_list):
            if p.error_dist == "normal" or p.model_type == "static":
                Z[:, :, i] = self.rng.standard_normal((n_paths, horizon))
            else:
                nu  = float(max(nu_v[i], 2.5))
                raw = self.rng.standard_t(df=nu, size=(n_paths, horizon))
                Z[:, :, i] = raw / np.sqrt(nu / (nu - 2.0))
        return Z

    # ── Audit logging ─────────────────────────────────────────────────────────

    def _build_audit(
        self,
        n_paths:      int,
        horizon:      int,
        elapsed:      float,
        garch_params: Optional[Dict[str, GARCHParams]],
        regime_state: Optional[RegimeState],
    ) -> dict:
        meta: dict = {
            "simulation_timestamp": pd.Timestamp.now().isoformat(),
            "seed":                 self.config.seed,
            "config":               self.config.to_dict(),
            "n_paths":              n_paths,
            "horizon":              horizon,
            "n_assets":             len(self._symbols),
            "symbols":              list(self._symbols),
            "elapsed_seconds":      round(elapsed, 3),
        }
        if garch_params:
            meta["garch_summary"] = {
                s: {
                    "model_type":  p.model_type,
                    "sigma_t":     round(p.sigma_t, 6),
                    "persistence": round(p.persistence, 4),
                    "aic":         round(p.aic, 1),
                    "warnings":    p.fit_warnings,
                }
                for s, p in garch_params.items()
            }
        if regime_state:
            meta["regime_state"] = regime_state.to_dict()
        return meta

    @staticmethod
    def _log_audit(metadata: dict) -> None:
        """Emit structured audit record to logger."""
        lines = [
            "=" * 62,
            "  SIMULATION AUDIT LOG",
            f"  Timestamp        : {metadata['simulation_timestamp']}",
            f"  Seed             : {metadata['seed']}",
            f"  Volatility model : {metadata['config']['volatility_model']}",
            f"  Regime model     : {metadata['config']['regime_model']}",
            f"  Paths x Horizon  : {metadata['n_paths']} x {metadata['horizon']}",
            f"  Assets           : {metadata['n_assets']}",
            f"  Elapsed          : {metadata['elapsed_seconds']:.3f}s",
        ]
        if "garch_summary" in metadata:
            lines.append("  GARCH per asset :")
            for sym, g in metadata["garch_summary"].items():
                warn = " [!]" if g["warnings"] else ""
                lines.append(
                    f"    {sym:<14} {g['model_type']:<11} "
                    f"sigma_t={g['sigma_t']:.5f}  persist={g['persistence']:.4f}"
                    f"  AIC={g['aic']:.1f}{warn}"
                )
        if "regime_state" in metadata:
            rs = metadata["regime_state"]
            lines.append(
                f"  Regime state     : {rs['regime_label_en']}"
                f"  ({rs['regime_confidence']:.1%} confidence)"
            )
            dur = rs["expected_duration_days"][rs["current_regime"]]
            lines.append(f"  Expected duration: {dur:.1f} trading days")
        lines.append("=" * 62)
        logger.info("\n".join(lines))

    # ── Serialisation ─────────────────────────────────────────────────────────

    def metadata_to_json(self) -> str:
        """
        Export the last simulation metadata as JSON (for audit trail).
        Call after simulate_paths().
        """
        if not self._is_fitted:
            return json.dumps({"error": "not fitted"})
        out: dict = {"config": self.config.to_dict()}
        if self._garch:
            out["garch"] = json.loads(self._garch.params_to_json())
        if self._regime:
            out["regime"] = self._regime.get_regime_state().to_dict()
        return json.dumps(out, indent=2)


# ── Utility (used internally and by diagnostics) ──────────────────────────────

def _nearest_psd(A: np.ndarray) -> np.ndarray:
    """Higham nearest-PSD: clip negative eigenvalues, renormalise diagonal."""
    eigvals, eigvecs = np.linalg.eigh(A)
    eigvals = np.maximum(eigvals, 1e-8)
    B = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.sqrt(np.diag(B))
    d[d < 1e-12] = 1.0
    return B / np.outer(d, d)


# ── Standalone smoke-test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-8s %(message)s")

    rng      = np.random.default_rng(1)
    T, N     = 500, 5
    symbols  = ["COMI.CA", "ESRS.CA", "TMGH.CA", "SWDY.CA", "HRHO.CA"]
    returns  = pd.DataFrame(
        rng.standard_normal((T, N)) * 0.015,
        columns=symbols
    )
    idx_ret  = returns.mean(axis=1)

    for vm, rm in [("static", "none"), ("gjr_garch", "none"), ("gjr_garch", "hmm")]:
        cfg    = SimulationConfig(volatility_model=vm, regime_model=rm,
                                  n_paths=500, horizon=63, seed=42)
        eng    = SimulationEngine(cfg)
        eng.fit(returns, index_returns=idx_ret)
        result = eng.simulate_paths()
        rp     = result.return_paths
        print(f"\n  [{vm} + {rm}] paths={rp.shape} "
              f"mean={rp.mean():.5f}  std={rp.std():.5f}")
        if result.regime_paths is not None:
            print(f"    regime_paths shape: {result.regime_paths.shape}")
