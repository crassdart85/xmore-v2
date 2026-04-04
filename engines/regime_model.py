"""
HMM Regime-Switching Layer — Phase 2
======================================
Identifies latent market regimes from index-level return features using a
Gaussian Hidden Markov Model.  Regime-conditional parameters are used to
initialise and re-initialise the GARCH process inside the simulation core.

Design choices
--------------
- HMM is fit on the *market index* (EGX30), not individual assets — regime
  is a portfolio-wide state, not asset-specific.
- Features: 20-day realised vol (most discriminative), 1-day log-return,
  60-day momentum (optional).  All standardised before fitting.
- K selection: AIC/BIC comparison of K=2 and K=3 when use_auto_select=True.
- Regimes are labelled by ascending annualised volatility so that regime 0 is
  always "Calm" and the highest index is always "Crisis" / "Turbulent".
- Viterbi decoding surfaces the most-likely historical state sequence for
  interpretability and audit.

Dependencies
------------
    pip install hmmlearn
"""

from __future__ import annotations

import json
import logging
import pickle
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Optional dep ─────────────────────────────────────────────────────────────

try:
    from hmmlearn import hmm as _hmm_lib
    HAS_HMMLEARN = True
except ImportError:                                 # pragma: no cover
    HAS_HMMLEARN = False
    logger.warning("hmmlearn not installed — HMM regime model unavailable.")


# ── Labels ───────────────────────────────────────────────────────────────────

_LABELS_EN: Dict[int, List[str]] = {
    2: ["Calm",    "Turbulent"],
    3: ["Calm",    "Turbulent", "Crisis"],
}
_LABELS_AR: Dict[int, List[str]] = {
    2: ["هادئ",   "متقلب"],
    3: ["هادئ",   "متقلب",    "أزمة"],
}


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class RegimeState:
    """
    Full description of the current market regime and forward transition
    probabilities.  Intended as the risk-dashboard input.
    """

    n_regimes:             int
    current_regime:        int               # 0-indexed, vol-sorted
    regime_label_en:       str
    regime_label_ar:       str
    regime_confidence:     float             # P(S_t = current | data)

    posterior_probs:       List[float]       # P(S_t = k | data), length n_regimes
    transition_matrix:     List[List[float]] # P[i][j] vol-sorted
    expected_duration_days: List[float]      # 1/(1 - P[k][k])
    one_step_transitions:  List[float]       # row for current regime

    regime_means:          List[float]       # daily mean return per regime (decimal)
    regime_vols:           List[float]       # annualised vol per regime (decimal)

    aic: float
    bic: float

    def summary(self) -> str:
        labels = _LABELS_EN.get(self.n_regimes, [f"Regime {k}" for k in range(self.n_regimes)])
        lines  = [
            f"Current Regime : {self.regime_label_en}  "
            f"(confidence {self.regime_confidence:.1%})",
            f"Expected Duration: {self.expected_duration_days[self.current_regime]:.1f} trading days",
            "Transition probs from current regime:",
        ]
        for j, (lbl, prob) in enumerate(zip(labels, self.one_step_transitions)):
            lines.append(f"  -> {lbl:12s}: {prob:.1%}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "n_regimes":              self.n_regimes,
            "current_regime":         self.current_regime,
            "regime_label_en":        self.regime_label_en,
            "regime_label_ar":        self.regime_label_ar,
            "regime_confidence":      round(self.regime_confidence, 4),
            "posterior_probs":        [round(x, 4) for x in self.posterior_probs],
            "transition_matrix":      [[round(x, 4) for x in row]
                                       for row in self.transition_matrix],
            "expected_duration_days": [round(x, 2) for x in self.expected_duration_days],
            "one_step_transitions":   [round(x, 4) for x in self.one_step_transitions],
            "regime_means":           [round(x, 6) for x in self.regime_means],
            "regime_vols":            [round(x, 4) for x in self.regime_vols],
            "aic":                    round(self.aic, 2),
            "bic":                    round(self.bic, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RegimeState":
        return cls(**d)


# ── Main class ───────────────────────────────────────────────────────────────

class RegimeModel:
    """
    Gaussian HMM for latent market-state detection.

    Workflow
    --------
    1.  model = RegimeModel(n_regimes=2, use_auto_select=True)
    2.  state = model.fit(index_returns)   # pd.Series of daily log-returns
    3.  print(state.summary())
    4.  regime_paths = model.simulate_regime_paths(n_paths=5000, horizon=252)
    5.  model.to_pickle("regime_state.pkl")
    """

    def __init__(
        self,
        n_regimes:        int  = 2,
        use_auto_select:  bool = True,
        seed:             int  = 42,
        n_iter:           int  = 200,
        covariance_type:  str  = "full",
    ) -> None:
        """
        Parameters
        ----------
        n_regimes       : Number of latent states (2 or 3 recommended).
        use_auto_select : If True, fit K=2 and K=3 and select by BIC.
        seed            : RNG seed (set in hmmlearn and numpy).
        n_iter          : EM iteration limit.
        covariance_type : "full" | "diag" | "tied" — passed to GaussianHMM.
        """
        self.n_regimes       = n_regimes
        self.use_auto_select = use_auto_select
        self.seed            = seed
        self.n_iter          = n_iter
        self.covariance_type = covariance_type
        self.rng             = np.random.default_rng(seed)

        self._model:          Optional[object]       = None  # GaussianHMM
        self._state:          Optional[RegimeState]  = None
        self._viterbi_states: Optional[np.ndarray]   = None  # integer, len T
        self._feature_mean:   Optional[np.ndarray]   = None  # shape (n_features,)
        self._feature_std:    Optional[np.ndarray]   = None
        self._vol_order:      Optional[np.ndarray]   = None  # index sort by vol

    # ── Public API ───────────────────────────────────────────────────────────

    def fit(self, index_returns: pd.Series) -> RegimeState:
        """
        Fit HMM on market-index return features.

        Parameters
        ----------
        index_returns : Daily log-returns of the market index (EGX30 etc.).
                        DatetimeIndex; at least 252 observations recommended.

        Returns
        -------
        RegimeState summarising the current market state.
        """
        if not HAS_HMMLEARN:
            raise ImportError("hmmlearn is required. Run: pip install hmmlearn")

        features = self._build_features(index_returns)

        if self.use_auto_select:
            self._model = self._select_by_bic(features)
        else:
            self._model = self._fit_single_model(features, self.n_regimes)

        self._viterbi_states = self._decode_viterbi(features)
        self._state          = self._build_regime_state(features, index_returns)
        return self._state

    def get_regime_state(self) -> RegimeState:
        if self._state is None:
            raise RuntimeError("Call fit() first.")
        return self._state

    def sample_initial_regimes(self, n_paths: int) -> np.ndarray:
        """
        Sample initial regime index for each path from current posterior
        probabilities P(S_t = k | all data).

        Returns
        -------
        np.ndarray shape (n_paths,), integer dtype.
        """
        if self._state is None:
            raise RuntimeError("Call fit() first.")
        probs = np.array(self._state.posterior_probs)
        probs = probs / probs.sum()                    # ensure normalised
        K = len(probs)                                 # authoritative from state
        return self.rng.choice(K, size=n_paths, p=probs)

    def simulate_regime_paths(self, n_paths: int, horizon: int) -> np.ndarray:
        """
        Simulate Markov regime sequences for all paths.

        Each path begins in a regime sampled from the current posterior.
        Subsequent steps transition according to the fitted transition matrix.

        Returns
        -------
        np.ndarray shape (n_paths, horizon), int32.
        """
        if self._model is None:
            raise RuntimeError("Call fit() first.")

        P_sorted = self._get_sorted_transmat()          # (n_regimes, n_regimes)
        P_cum    = np.cumsum(P_sorted, axis=1)          # cumulative row probabilities

        regime_paths        = np.empty((n_paths, horizon), dtype=np.int32)
        regime_paths[:, 0]  = self.sample_initial_regimes(n_paths)

        # Pre-draw uniform samples: (n_paths, horizon-1)
        U = self.rng.random((n_paths, horizon - 1))

        for t in range(1, horizon):
            prev      = regime_paths[:, t - 1]           # (n_paths,)
            thresholds = P_cum[prev]                      # (n_paths, n_regimes)
            # First regime j where U < cumprob[j]
            regime_paths[:, t] = (U[:, t - 1:t] < thresholds).argmax(axis=1)

        return regime_paths

    def get_regime_volatilities(self) -> np.ndarray:
        """
        Annualised daily volatility per regime (decimal), shape (n_regimes,).
        Regimes are ordered by ascending volatility.
        """
        if self._state is None:
            raise RuntimeError("Call fit() first.")
        return np.array(self._state.regime_vols)

    def get_viterbi_states(self) -> Optional[np.ndarray]:
        """Most-likely state sequence over historical data (Viterbi decoded)."""
        return self._viterbi_states

    def to_pickle(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def from_pickle(cls, path: str) -> "RegimeModel":
        with open(path, "rb") as f:
            return pickle.load(f)

    def state_to_json(self) -> str:
        if self._state is None:
            raise RuntimeError("Call fit() first.")
        return json.dumps(self._state.to_dict(), indent=2)

    # ── Private: feature engineering ─────────────────────────────────────────

    def _build_features(self, returns: pd.Series) -> np.ndarray:
        """
        Construct (T, 3) feature matrix from index returns.

        Features
        --------
        0 : 20-day rolling realised volatility (annualised)
        1 : 1-day log-return
        2 : 60-day rolling momentum (annualised mean return)
        """
        df             = pd.DataFrame({"ret": returns.values},
                                       index=returns.index)
        df["rvol20"]   = df["ret"].rolling(20).std()  * np.sqrt(252)
        df["ret1d"]    = df["ret"]
        df["mom60"]    = df["ret"].rolling(60).mean() * 252
        df             = df.dropna()

        X = df[["rvol20", "ret1d", "mom60"]].values.astype(np.float64)

        # Standardise (z-score) so all features have unit scale
        self._feature_mean = X.mean(axis=0)
        self._feature_std  = np.maximum(X.std(axis=0), 1e-8)
        return (X - self._feature_mean) / self._feature_std

    # ── Private: model fitting ────────────────────────────────────────────────

    def _fit_single_model(self, features: np.ndarray, k: int):
        """Fit one GaussianHMM and return it."""
        model = _hmm_lib.GaussianHMM(
            n_components    = k,
            covariance_type = self.covariance_type,
            n_iter          = self.n_iter,
            random_state    = self.seed,
            tol             = 1e-5,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(features)
        # Note: caller (_select_by_bic) is responsible for setting self.n_regimes
        # to the winning K; _fit_single_model must not clobber it unconditionally.
        return model

    def _select_by_bic(self, features: np.ndarray):
        """Fit K=2 and K=3; return model with lowest BIC."""
        T         = len(features)
        best_bic  = float("inf")
        best_model = None

        for k in [2, 3]:
            try:
                mdl      = self._fit_single_model(features, k)
                log_p    = mdl.score(features)
                n_params = self._count_params(mdl, features.shape[1])
                bic      = -2.0 * log_p + n_params * np.log(T)
                aic      = -2.0 * log_p + 2.0 * n_params
                logger.info("HMM K=%d | log-prob=%.1f | AIC=%.1f | BIC=%.1f",
                            k, log_p, aic, bic)
                if bic < best_bic:
                    best_bic   = bic
                    best_model = mdl
                    self.n_regimes = k
            except Exception as exc:
                logger.warning("HMM K=%d failed: %s", k, exc)

        if best_model is None:
            raise RuntimeError("All HMM fits failed.")
        self.n_regimes = best_model.n_components   # ensure consistent with winner
        return best_model

    # ── Private: decoding and state extraction ────────────────────────────────

    def _decode_viterbi(self, features: np.ndarray) -> np.ndarray:
        """
        Return Viterbi most-likely regime sequence (vol-sorted labels).
        Shape: (T,), int.
        """
        raw_states = self._model.predict(features)
        order      = self._get_vol_sort_order()   # raw -> vol-sorted mapping
        inverse    = np.argsort(order)            # vol-sorted index for raw label k
        return inverse[raw_states].astype(np.int32)

    def _build_regime_state(
        self, features: np.ndarray, returns: pd.Series
    ) -> RegimeState:
        """
        Extract full RegimeState from fitted model and feature matrix.
        """
        mdl = self._model
        K   = mdl.n_components     # authoritative; avoids self.n_regimes race
        order = self._get_vol_sort_order()        # indices that sort by vol (ascending)

        # ── Posterior probabilities at most recent observation ─────────────
        posteriors_raw    = mdl.predict_proba(features)     # (T, K_raw)
        last_post_raw     = posteriors_raw[-1]               # (K_raw,)
        last_post_sorted  = last_post_raw[order]             # vol-sorted
        current_regime    = int(np.argmax(last_post_sorted))

        # ── Transition matrix (re-ordered) ────────────────────────────────
        P_sorted = self._get_sorted_transmat()

        # ── Expected duration per regime ──────────────────────────────────
        durations = [1.0 / max(1.0 - P_sorted[k, k], 1e-6) for k in range(K)]

        # ── Regime-conditional return and vol ─────────────────────────────
        # means_ shape: (K_raw, n_features); back-transform feature 0 (rvol20)
        # and feature 1 (ret1d) from standardised space
        means_sorted = mdl.means_[order]           # (K, n_features)
        regime_means = []
        regime_vols  = []
        for k in range(K):
            # Back-transform daily return (feature 1)
            ret_mu = (means_sorted[k, 1] * self._feature_std[1]
                      + self._feature_mean[1])
            # Back-transform annualised realised vol (feature 0)
            rvol_ann = (means_sorted[k, 0] * self._feature_std[0]
                        + self._feature_mean[0])
            regime_means.append(float(ret_mu))
            regime_vols.append(float(max(rvol_ann, 0.001)))

        # ── Model quality ─────────────────────────────────────────────────
        T       = len(features)
        log_p   = float(mdl.score(features))
        n_par   = self._count_params(mdl, features.shape[1])
        aic     = -2.0 * log_p + 2.0 * n_par
        bic     = -2.0 * log_p + n_par * np.log(T)

        # ── Labels ────────────────────────────────────────────────────────
        labels_en = _LABELS_EN.get(K, [f"Regime {k}" for k in range(K)])
        labels_ar = _LABELS_AR.get(K, [f"نظام {k}"   for k in range(K)])

        return RegimeState(
            n_regimes             = K,
            current_regime        = current_regime,
            regime_label_en       = labels_en[current_regime],
            regime_label_ar       = labels_ar[current_regime],
            regime_confidence     = float(last_post_sorted[current_regime]),
            posterior_probs       = last_post_sorted.tolist(),
            transition_matrix     = P_sorted.tolist(),
            expected_duration_days= durations,
            one_step_transitions  = P_sorted[current_regime].tolist(),
            regime_means          = regime_means,
            regime_vols           = regime_vols,
            aic                   = float(aic),
            bic                   = float(bic),
        )

    # ── Private: helpers ─────────────────────────────────────────────────────

    def _get_vol_sort_order(self) -> np.ndarray:
        """
        Return permutation that sorts raw regime indices by ascending
        annualised realised volatility (feature 0).
        Cached after first call.
        """
        if self._vol_order is None:
            raw_vol_std = self._model.means_[:, 0]   # feature-0 mean (standardised)
            self._vol_order = np.argsort(raw_vol_std)
        return self._vol_order

    def _get_sorted_transmat(self) -> np.ndarray:
        """Transition matrix re-ordered to vol-sorted regime indices."""
        order = self._get_vol_sort_order()
        P_raw = self._model.transmat_
        return P_raw[np.ix_(order, order)]

    @staticmethod
    def _count_params(model, n_features: int) -> int:
        """Count free parameters for BIC/AIC computation."""
        K = model.n_components
        # Transition matrix rows sum to 1: K*(K-1) free
        # Initial probs sum to 1: K-1 free
        # Means: K * n_features
        # Covariance: depends on type
        cov_type = model.covariance_type
        if cov_type == "full":
            cov_par = K * n_features * (n_features + 1) // 2
        elif cov_type == "diag":
            cov_par = K * n_features
        elif cov_type == "tied":
            cov_par = n_features * (n_features + 1) // 2
        else:
            cov_par = K * n_features
        return K * (K - 1) + (K - 1) + K * n_features + cov_par


# ── Quick regime query (works with or without hmmlearn) ─────────────────────

def get_current_regime(symbol: str, price_series: pd.Series) -> dict:
    """
    Return current regime classification for a given symbol.

    Attempts HMM fit first (if hmmlearn is installed and >= 252 observations).
    Falls back to deterministic MA/vol classification.

    Returns:
        {
            'regime': int,                    # 0 or 1 (or 2 for 3-state)
            'regime_label': str,              # 'bull' | 'bear' | 'high_vol' | 'calm' | 'unknown'
            'regime_probability': float,      # P(current state) from HMM, or 0.80 for MA/vol
            'regime_stable': bool,            # Same regime for last 5+ days
            'vol_regime': float,              # Current regime mean vol (annualised)
            'drift_regime': float,            # Current regime mean return (daily)
        }

    If fit fails: regime_label='unknown', regime_probability=0.0
    """
    result = {
        'regime': 0,
        'regime_label': 'unknown',
        'regime_probability': 0.0,
        'regime_stable': True,
        'vol_regime': 0.0,
        'drift_regime': 0.0,
    }

    if price_series is None or len(price_series) < 20:
        return result

    try:
        # Compute daily log-returns
        log_ret = np.log(price_series / price_series.shift(1)).dropna()

        # Try HMM if installed and enough data
        if HAS_HMMLEARN and len(log_ret) >= 252:
            try:
                model = RegimeModel(n_regimes=2, use_auto_select=True, seed=42)
                state = model.fit(log_ret)

                # Map HMM labels to bull/bear/high_vol
                label = state.regime_label_en.lower()
                if label == 'calm':
                    regime_label = 'bull' if state.regime_means[state.current_regime] > 0 else 'bear'
                elif label in ('turbulent', 'crisis'):
                    regime_label = 'high_vol'
                else:
                    regime_label = label

                # Check stability (same regime for last 5 days)
                viterbi = model.get_viterbi_states()
                regime_stable = True
                if viterbi is not None and len(viterbi) >= 5:
                    regime_stable = len(set(viterbi[-5:])) == 1

                return {
                    'regime': state.current_regime,
                    'regime_label': regime_label,
                    'regime_probability': state.regime_confidence,
                    'regime_stable': regime_stable,
                    'vol_regime': state.regime_vols[state.current_regime],
                    'drift_regime': state.regime_means[state.current_regime],
                }
            except Exception as e:
                logger.debug("HMM fit failed for %s, falling back to MA/vol: %s", symbol, e)

        # Fallback: deterministic MA/vol classification
        closes = price_series.dropna()
        if len(closes) < 20:
            return result

        ma20 = float(closes.tail(20).mean())
        price = float(closes.iloc[-1])
        vol20 = float(closes.pct_change().dropna().tail(20).std())
        vol_ann = vol20 * np.sqrt(252)
        daily_ret = float(closes.pct_change().dropna().tail(20).mean())
        bearish = price < ma20
        deviation = (price / ma20) - 1

        if bearish and (deviation < -0.03 or vol20 > 0.025):
            regime_label = 'high_vol'
            regime_idx = 1
        elif daily_ret > 0 and not bearish:
            regime_label = 'bull'
            regime_idx = 0
        elif bearish:
            regime_label = 'bear'
            regime_idx = 1
        else:
            regime_label = 'bull'
            regime_idx = 0

        return {
            'regime': regime_idx,
            'regime_label': regime_label,
            'regime_probability': 0.80,
            'regime_stable': True,  # MA/vol doesn't track day-over-day transitions
            'vol_regime': vol_ann,
            'drift_regime': daily_ret,
        }

    except Exception as e:
        logger.warning("get_current_regime failed for %s: %s", symbol, e)
        return result


# ── Standalone smoke-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-8s %(message)s")

    rng = np.random.default_rng(0)
    T   = 600
    # Synthetic 2-regime returns: low-vol period then high-vol period
    idx_returns = pd.Series(
        np.concatenate([
            rng.normal(0.0003, 0.008, T // 2),
            rng.normal(-0.001, 0.022, T // 2),
        ]),
        name="EGX30"
    )

    mdl   = RegimeModel(n_regimes=2, use_auto_select=True, seed=42)
    state = mdl.fit(idx_returns)
    print("\n" + state.summary())

    paths = mdl.simulate_regime_paths(n_paths=100, horizon=22)
    print(f"\n  Regime paths shape: {paths.shape}")
    occupancy = np.bincount(paths.ravel(), minlength=state.n_regimes)
    for k, (lbl, cnt) in enumerate(
        zip(_LABELS_EN.get(state.n_regimes, []), occupancy)
    ):
        print(f"  Regime {k} ({lbl}): {cnt / paths.size:.1%} of path-steps")
