"""
ML LightGBM Agent

Uses LightGBM gradient-boosted trees with 40+ TA-Lib technical indicators.
Implements walk-forward validation (TimeSeriesSplit) to prevent look-ahead bias.
Applies feature selection (top-20 by gain importance) and Optuna hyperparameter
tuning (cached per symbol) to maximise OOS accuracy.

Three major signal-quality improvements over the original RF model:
  1. Per-symbol models    — stock-specific patterns; global fallback for thin data
  2. Confidence gating    — UP/DOWN only emitted when max P(class) >= 0.65
  3. Optuna tuning        — 25-trial TPE search cached in model file (runs once)
"""

import pandas as pd
import numpy as np
import joblib
import os
import warnings
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from lightgbm import LGBMClassifier
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False
    from sklearn.ensemble import RandomForestClassifier
    logger.warning(
        "LightGBM not installed; falling back to RandomForestClassifier. "
        "Install lightgbm for best performance (faster training and better accuracy)."
    )

from agents.agent_base import BaseAgent, AgentSignal
from features import (add_technical_indicators, add_sentiment_features,
                      add_macro_features, add_crosssectional_features,
                      get_feature_columns, log_feature_importance)
from database import get_connection

class PurgedTimeSeriesSplit:
    """
    Walk-forward CV with a purge gap between each train and test fold.
    The 5-day return label creates overlap across consecutive rows, so the
    `purge_gap` most recent training rows are dropped to prevent leakage.
    """
    def __init__(self, n_splits: int = 5, purge_gap: int = 5):
        self.n_splits  = n_splits
        self.purge_gap = purge_gap

    def split(self, X, y=None, groups=None):
        n         = len(X)
        indices   = np.arange(n)
        fold_size = n // (self.n_splits + 1)
        for i in range(self.n_splits):
            test_start = (i + 1) * fold_size
            test_end   = min(test_start + fold_size, n)
            train_end  = test_start - self.purge_gap
            if train_end < 10 or test_end > n:
                continue
            yield indices[:train_end], indices[test_start:test_end]


def _compute_regime_labels(df: pd.DataFrame) -> np.ndarray:
    """
    Classify each row as 'calm' or 'turbulent' using MA20 / vol20 rules.
    Matches the deterministic regime detector in run_agents.py.
    """
    close  = df['close'].values.astype(float)
    n      = len(close)
    labels = np.full(n, 'calm', dtype=object)
    for i in range(20, n):
        window = close[i - 20:i]
        ma20   = float(window.mean())
        if ma20 <= 0:
            continue
        pct_returns = np.diff(window) / window[:-1]
        vol20 = float(np.std(pct_returns))
        price = close[i]
        if price < ma20 and ((price / ma20 - 1 < -0.03) or (vol20 > 0.025)):
            labels[i] = 'turbulent'
    return labels


def _detect_current_regime(df: pd.DataFrame) -> str:
    """Return current regime ('calm' or 'turbulent') from the last row of OHLCV data."""
    try:
        close = df['close'].values.astype(float)
        if len(close) < 20:
            return 'calm'
        window = close[-20:]
        ma20   = float(window.mean())
        if ma20 <= 0:
            return 'calm'
        pct_returns = np.diff(window) / window[:-1]
        vol20 = float(np.std(pct_returns))
        price = close[-1]
        if price < ma20 and ((price / ma20 - 1 < -0.03) or (vol20 > 0.025)):
            return 'turbulent'
    except Exception:
        pass
    return 'calm'


MODEL_DIR = 'models'
MODEL_MAX_AGE_DAYS = 7    # Force retrain if saved model is older than this

# Prediction return thresholds
UP_THRESHOLD   =  0.005   # +0.5% = UP
DOWN_THRESHOLD = -0.005   # -0.5% = DOWN

# Feature selection
_TOP_N_FEATURES = 20      # Keep top-N by gain importance after WFV
_MIN_FEATURES   = 10      # Never drop below this many features

# Confidence gating — suppress low-confidence directional signals
CONFIDENCE_THRESHOLD = 0.65  # Only emit UP/DOWN if max(P) >= 65%

# Optuna hyperparameter tuning
OPTUNA_N_TRIALS = int(os.environ.get('OPTUNA_N_TRIALS', '25'))  # Override via env var in CI
OPTUNA_TIMEOUT  = 60     # Hard ceiling in seconds per symbol (was 90)


def _model_path(symbol: str) -> str:
    """Symbol-specific model path, e.g. models/COMI_CA_predictor.pkl"""
    safe = symbol.replace('.', '_').replace('/', '_').replace('\\', '_')
    return os.path.join(MODEL_DIR, f'{safe}_predictor.pkl')


def _select_top_features(model, features: list, top_n: int = _TOP_N_FEATURES) -> list:
    """
    Return top_n features by LightGBM gain importance.
    Gain importance (total information gain per feature) is more informative
    than split count for feature selection.
    Falls back to all features if importances are unavailable.
    """
    try:
        if hasattr(model, 'booster_'):
            importances = model.booster_.feature_importance(importance_type='gain')
        elif hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        else:
            return features
        paired = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
        selected = [f for f, _ in paired[:top_n]]
        if len(selected) >= _MIN_FEATURES:
            return selected
    except Exception as e:
        logger.warning(f"Feature selection failed: {e}")
    return features


def _make_lgbm(**kwargs) -> 'LGBMClassifier':
    """
    Build a LGBMClassifier with production-ready defaults for EGX financial data.
    kwargs override any default (used for Optuna-tuned params).
    """
    params = dict(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        num_leaves=31,
        class_weight='balanced',
        min_child_samples=10,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    params.update(kwargs)
    return LGBMClassifier(**params)


def _tune_lgbm_params(X: pd.DataFrame, y: pd.Series) -> Optional[dict]:
    """
    Use Optuna TPE to search LightGBM hyperparameters via walk-forward CV.

    Runs OPTUNA_N_TRIALS trials with a OPTUNA_TIMEOUT-second wall-clock ceiling.
    On small EGX datasets (~100-300 rows) each trial takes ~0.05-0.1s, so 25
    trials completes in ~3s — fast enough for the daily pipeline.

    Returns best params dict, or None if Optuna is unavailable or search fails.
    """
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        return None

    if not LGBM_AVAILABLE:
        return None

    n_splits = min(3, len(X) // 20)
    if n_splits < 2:
        return None

    tscv = TimeSeriesSplit(n_splits=n_splits)

    def objective(trial):
        params = {
            'n_estimators':      trial.suggest_int('n_estimators', 100, 500),
            'max_depth':         trial.suggest_int('max_depth', 3, 8),
            'learning_rate':     trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
            'num_leaves':        trial.suggest_int('num_leaves', 15, 63),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 30),
            'subsample':         trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree':  trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'class_weight': 'balanced', 'random_state': 42, 'n_jobs': -1, 'verbose': -1,
        }
        scores = []
        for train_idx, test_idx in tscv.split(X):
            m = LGBMClassifier(**params)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                m.fit(X.iloc[train_idx], y.iloc[train_idx])
            scores.append(m.score(X.iloc[test_idx], y.iloc[test_idx]))
        return float(np.mean(scores))

    try:
        study = optuna.create_study(direction='maximize')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            study.optimize(objective, n_trials=OPTUNA_N_TRIALS,
                           timeout=OPTUNA_TIMEOUT, show_progress_bar=False)
        return study.best_params
    except Exception as e:
        logger.warning(f"Optuna tuning failed: {e}")
        return None


class MLAgent(BaseAgent):
    def __init__(self):
        super().__init__("ML_RandomForest")
        self._model_cache: dict = {}   # {symbol: {'model': m, 'feature_names': [...], 'regime_models': {...}, 'model_10d': ...}}
        self.model = None
        self.feature_names = None
        self._regime_models: Dict[str, Any] = {}
        self._model_10d = None
        self._last_probs = None
        self._last_top_features = None
        self._last_training_accuracy = None
        self._last_samples_used = None
        # Models are loaded lazily per symbol in predict() — no preload here

    def load_model(self, symbol: str = ''):
        """
        Load symbol-specific model if it exists and is not stale.
        Updates self.model and self.feature_names.
        """
        path = _model_path(symbol) if symbol else os.path.join(MODEL_DIR, 'stock_predictor.pkl')
        if not os.path.exists(path):
            logger.info(f"[{symbol}] No saved model at {path} — will train on-the-fly")
            return
        try:
            data = joblib.load(path)
            if not isinstance(data, dict):
                logger.info(f"[{symbol}] Legacy model format — will retrain")
                return
            trained_at = data.get('trained_at')
            if trained_at:
                age_days = (datetime.now() - datetime.fromisoformat(trained_at)).days
                if age_days > MODEL_MAX_AGE_DAYS:
                    logger.info(
                        f"[{symbol}] Model is {age_days}d old (>{MODEL_MAX_AGE_DAYS}d) — will retrain"
                    )
                    return
            self.model = data.get('model')
            self.feature_names = data.get('feature_names', get_feature_columns())
            self._regime_models = data.get('regime_models', {})
            self._model_10d = data.get('model_10d')
            logger.info(f"[{symbol}] Model loaded from {path} (trained {trained_at})")
        except Exception as e:
            logger.error(f"[{symbol}] Error loading model: {e}")

    def save_model(self, model, feature_names: list, symbol: str = '',
                   best_params: Optional[dict] = None,
                   regime_models: Optional[Dict[str, Any]] = None,
                   model_10d=None):
        """Save symbol-specific model with metadata."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = _model_path(symbol) if symbol else os.path.join(MODEL_DIR, 'stock_predictor.pkl')
        data = {
            'model':         model,
            'feature_names': feature_names,
            'trained_at':    datetime.now().isoformat(),
            'best_params':   best_params,   # Cached Optuna params; None = use defaults
            'regime_models': regime_models or {},
            'model_10d':     model_10d,     # 10-day horizon model (None if too little data)
        }
        joblib.dump(data, path)
        logger.info(f"[{symbol}] Model saved to {path}")

    def _load_cached_params(self, symbol: str) -> Optional[dict]:
        """Return Optuna-tuned params from saved model file, if available."""
        path = _model_path(symbol)
        if not os.path.exists(path):
            return None
        try:
            data = joblib.load(path)
            return data.get('best_params') if isinstance(data, dict) else None
        except Exception:
            return None

    def predict(self, price_df: pd.DataFrame,
                sentiment: Optional[Dict[str, Any]] = None) -> str:
        """
        Predict using a per-symbol LightGBM model.
        If no fresh model exists, trains one on the fly (with Optuna tuning).
        Applies a confidence gate: UP/DOWN is suppressed to HOLD when
        max(P) < CONFIDENCE_THRESHOLD (0.60).
        """
        symbol = price_df.iloc[0]['symbol'] if 'symbol' in price_df.columns else 'UNKNOWN'

        df = price_df.copy()

        news_df = pd.DataFrame()
        macro_df = pd.DataFrame()
        if symbol and symbol != 'UNKNOWN':
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    if os.getenv('DATABASE_URL'):
                        cur.execute("SELECT date, sentiment_score FROM news WHERE symbol=%s", (symbol,))
                    else:
                        cur.execute("SELECT date, sentiment_score FROM news WHERE symbol=?", (symbol,))
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                    news_df = pd.DataFrame([dict(zip(cols, r)) for r in rows])
            except Exception as exc:
                logger.debug(f"[{symbol}] Failed to load sentiment rows: {exc}")

        # Macro context (Brent, USD/EGP, EM)
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT date,
                        MAX(CASE WHEN symbol='MACRO_BRENT'  THEN close END) AS brent_close,
                        MAX(CASE WHEN symbol='MACRO_USDSAR' THEN close END) AS usdsar_close,
                        MAX(CASE WHEN symbol='MACRO_EEM'    THEN close END) AS eem_close
                    FROM prices
                    WHERE symbol IN ('MACRO_BRENT', 'MACRO_USDSAR', 'MACRO_EEM')
                    GROUP BY date ORDER BY date
                """)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                macro_df = pd.DataFrame([dict(zip(cols, r)) for r in rows])
        except Exception as exc:
            logger.debug(f"[{symbol}] Failed to load macro context: {exc}")

        df = add_technical_indicators(df)
        df = add_sentiment_features(df, news_df)
        df = add_macro_features(df, macro_df)

        # ── Cross-sectional features: stock vs TASI index ────────────────
        index_df = pd.DataFrame()
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                # TASI proxy: use 2222.SR (Saudi Aramco, most liquid, high correlation with index)
                cur.execute("""
                    SELECT date, close FROM prices
                    WHERE symbol = '2222.SR'
                    ORDER BY date
                """)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                index_df = pd.DataFrame([dict(zip(cols, r)) for r in rows])
        except Exception as exc:
            logger.debug(f"[{symbol}] Failed to load index proxy: {exc}")
        df = add_crosssectional_features(df, index_df if len(index_df) > 20 else None)

        all_features = get_feature_columns()
        available_features = [f for f in all_features
                              if f in df.columns and not df[f].isna().all()]

        if len(available_features) < 5:
            logger.warning(f"[{symbol}] Only {len(available_features)} features — using HOLD")
            return "HOLD"

        # ── Load or train per-symbol model ──────────────────────────────────
        if symbol not in self._model_cache:
            self.model = None
            self.feature_names = None
            self._regime_models = {}
            self._model_10d = None
            self.load_model(symbol)
            if self.model is not None:
                self._model_cache[symbol] = {
                    'model': self.model, 'feature_names': self.feature_names,
                    'regime_models': self._regime_models, 'model_10d': self._model_10d,
                }
        else:
            cached = self._model_cache[symbol]
            self.model = cached['model']
            self.feature_names = cached['feature_names']
            self._regime_models = cached.get('regime_models', {})
            self._model_10d = cached.get('model_10d')

        if self.model is None:
            self.model, self.feature_names = self._train_model(df, available_features, symbol)
            if self.model is not None:
                self._model_cache[symbol] = {
                    'model': self.model, 'feature_names': self.feature_names,
                    'regime_models': self._regime_models, 'model_10d': self._model_10d,
                }

        if self.model is None:
            return "HOLD"

        features = [f for f in self.feature_names if f in df.columns]
        if len(features) < len(self.feature_names) * 0.5:
            logger.warning(f"[{symbol}] Too many features missing — retraining")
            self.model, self.feature_names = self._train_model(df, available_features, symbol)
            if self.model is not None:
                self._model_cache[symbol] = {
                    'model': self.model, 'feature_names': self.feature_names,
                    'regime_models': self._regime_models, 'model_10d': self._model_10d,
                }
            features = available_features

        if self.model is None:
            return "HOLD"

        last_row = df.iloc[[-1]].copy()
        for feat in features:
            if feat in last_row.columns and last_row[feat].isna().any():
                last_row[feat] = 0

        try:
            X = last_row[features]

            # Use regime sub-model if available for the current market state
            current_regime = _detect_current_regime(df)
            active_model = self._regime_models.get(current_regime) or self.model
            if active_model is not self.model:
                logger.debug(f"[{symbol}] Using '{current_regime}' regime sub-model")

            probs_5d = active_model.predict_proba(X)[0]

            # Blend 5d and 10d horizon probabilities (60%/40% weight).
            # The 10d model captures multi-day trend persistence; the 5d model
            # is more reactive. Blending reduces noise from short-term reversals.
            if self._model_10d is not None:
                try:
                    probs_10d = self._model_10d.predict_proba(X)[0]
                    # Align class order (both models trained on same y encoding)
                    classes_5d  = list(active_model.classes_)
                    classes_10d = list(self._model_10d.classes_)
                    # Pad any missing class with 0
                    blended = np.zeros(3)
                    for cls_i in range(3):
                        p5  = probs_5d[classes_5d.index(cls_i)]  if cls_i in classes_5d  else 0.0
                        p10 = probs_10d[classes_10d.index(cls_i)] if cls_i in classes_10d else 0.0
                        blended[cls_i] = 0.60 * p5 + 0.40 * p10
                    blended /= blended.sum()  # renormalize
                    probs = blended
                    prediction = int(np.argmax(probs))
                except Exception as _blend_err:
                    logger.debug(f"[{symbol}] 10d blend failed: {_blend_err}")
                    probs = probs_5d
                    prediction = int(active_model.predict(X)[0])
            else:
                probs = probs_5d
                prediction = int(active_model.predict(X)[0])

            confidence = float(max(probs))

            # Build probs dict for predict_signal
            classes = self.model.classes_
            self._last_probs = {}
            mapping_inv = {0: "DOWN", 1: "FLAT", 2: "UP"}
            for i, cls in enumerate(classes):
                self._last_probs[mapping_inv.get(cls, str(cls))] = round(float(probs[i]), 3)

            # Top features by gain
            try:
                if hasattr(active_model, 'booster_'):
                    importances = active_model.booster_.feature_importance(importance_type='gain')
                else:
                    importances = active_model.feature_importances_
                feat_importance = sorted(
                    zip(features, importances), key=lambda x: x[1], reverse=True
                )[:5]
                self._last_top_features = [
                    {"name": fn, "importance": round(float(fi), 4),
                     "value": round(float(last_row[fn].iloc[0]) if fn in last_row.columns else 0, 4)}
                    for fn, fi in feat_importance
                ]
            except Exception as exc:
                logger.debug(f"[{symbol}] Unable to compute feature importances: {exc}")

            mapping = {0: "DOWN", 1: "FLAT", 2: "UP"}
            result = mapping.get(prediction, "HOLD")

            # ── Confidence gate ────────────────────────────────────────────
            if result in ('UP', 'DOWN') and confidence < CONFIDENCE_THRESHOLD:
                logger.info(
                    f"[{symbol}] Gated to HOLD: {result} confidence {confidence:.2f} "
                    f"< threshold {CONFIDENCE_THRESHOLD}"
                )
                result = 'HOLD'

            logger.info(f"[{symbol}] Prediction: {result} (max_prob={confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"[{symbol}] Prediction error: {e}")
            return "HOLD"

    def predict_signal(self, data: pd.DataFrame, symbol: str = "",
                       sentiment: Optional[Dict[str, Any]] = None,
                       market_config: Optional[Dict] = None) -> dict:
        """Generate structured prediction with class probabilities and top features."""
        # Inject symbol so predict() can use per-symbol model files
        if symbol and 'symbol' not in data.columns:
            data = data.copy()
            data['symbol'] = symbol
        prediction = self.predict(data, sentiment)

        class_probs = self._last_probs or {"UP": 0.33, "DOWN": 0.33, "FLAT": 0.34}
        top_features = self._last_top_features or []
        confidence = max(class_probs.values()) * 100 if class_probs else 50.0

        # Flag when gating was applied
        gated = (max(class_probs.values()) < CONFIDENCE_THRESHOLD
                 and prediction == 'HOLD'
                 and max(class_probs, key=class_probs.get) in ('UP', 'DOWN'))

        reasoning = {
            "class_probabilities":  class_probs,
            "top_features":         top_features,
            "training_accuracy":    round(self._last_training_accuracy or 0, 3),
            "samples_used":         self._last_samples_used or 0,
            "confidence_gated":     gated,
            "confidence_threshold": CONFIDENCE_THRESHOLD,
        }

        return AgentSignal(
            agent_name=self.name, symbol=symbol,
            prediction=prediction, confidence=round(confidence, 1),
            reasoning=reasoning
        ).to_dict()

    def _train_model(self, df: pd.DataFrame, features: list, symbol: str = ''):
        """
        Three-pass training with CPCV, focal weighting, and regime sub-models:

          Pass 1 — Optuna HPO (25 trials, cached once per symbol).
          Pass 2 — Purged walk-forward CV (CPCV, 5-day purge gap) to collect
                   OOF probabilities for focal sample weighting.
          Pass 3 — Final model on all data with focal weights + feature selection.
                   Also trains Calm/Turbulent regime sub-models on data subsets.
        """
        if not LGBM_AVAILABLE:
            return self._train_model_rf_fallback(df, features, symbol)

        df = df.copy()
        df['future_return']     = df['close'].shift(-5)  / df['close'] - 1
        df['future_return_10d'] = df['close'].shift(-10) / df['close'] - 1
        df['target'] = df['future_return'].apply(
            lambda x: 2 if x > UP_THRESHOLD else (0 if x < DOWN_THRESHOLD else 1)
        )
        df['target_10d'] = df['future_return_10d'].apply(
            lambda x: 2 if x > UP_THRESHOLD else (0 if x < DOWN_THRESHOLD else 1)
        )
        train_df = df.dropna(subset=['target', 'target_10d'] + features).copy()

        if len(train_df) < 30:
            logger.warning(f"[{symbol}] Not enough data ({len(train_df)} rows) — HOLD")
            return None, None

        X = train_df[features]
        y = train_df['target'].astype(int)

        # ── Pass 1: Optuna hyperparameter search ──────────────────────────
        best_params = self._load_cached_params(symbol) or {}
        if not best_params and len(train_df) >= 60:
            logger.info(f"[{symbol}] Running Optuna ({OPTUNA_N_TRIALS} trials)...")
            tuned = _tune_lgbm_params(X, y)
            if tuned:
                best_params = tuned
                logger.info(f"[{symbol}] Optuna best params: {best_params}")
            else:
                logger.info(f"[{symbol}] Optuna unavailable — using defaults")

        # ── Pass 2: Purged walk-forward CV (CPCV) ─────────────────────────
        # 5-day purge gap prevents leakage from the 5-day forward-return label.
        n_splits = min(5, len(X) // 10)
        if n_splits < 2:
            n_splits = 2

        tscv = PurgedTimeSeriesSplit(n_splits=n_splits, purge_gap=5)
        scores = []
        best_model = None
        best_score = 0.0

        # OOF probability of the correct class (for focal weighting)
        oof_p_correct = np.full(len(X), 0.5)

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            model = _make_lgbm(**best_params)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                model.fit(X_train, y_train)

            score = model.score(X_test, y_test)
            scores.append(score)

            if score > best_score:
                best_score = score
                best_model = model

            # Collect OOF probs: p_correct = P(true class)
            test_probs = model.predict_proba(X_test)
            classes = list(model.classes_)
            for local_i, (true_lbl, prob_row) in enumerate(zip(y_test.values, test_probs)):
                if true_lbl in classes:
                    oof_p_correct[test_idx[local_i]] = float(prob_row[classes.index(true_lbl)])

        if not scores:
            logger.warning(f"[{symbol}] No valid CV folds — using full data fallback")
            n_splits = 2
            from sklearn.model_selection import TimeSeriesSplit as _TSCV
            for train_idx, test_idx in _TSCV(n_splits=n_splits).split(X):
                model = _make_lgbm(**best_params)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    model.fit(X.iloc[train_idx], y.iloc[train_idx])
                score = model.score(X.iloc[test_idx], y.iloc[test_idx])
                scores.append(score)
                if score > best_score:
                    best_score = score
                    best_model = model

        avg_score = float(np.mean(scores)) if scores else 0.0
        self._last_training_accuracy = avg_score
        self._last_samples_used = len(train_df)
        logger.info(
            f"[{symbol}] LightGBM WFV avg={avg_score:.3f} (splits={n_splits}, "
            f"optuna={'yes' if best_params else 'defaults'})"
        )

        if best_model is None:
            return None, None

        # ── Feature selection ─────────────────────────────────────────────
        selected = _select_top_features(best_model, features, top_n=_TOP_N_FEATURES)
        if len(selected) < len(features):
            logger.info(f"[{symbol}] Features: {len(features)} → {len(selected)}")

        # ── Focal sample weights: w = (1 - p_correct)^gamma ──────────────
        FOCAL_GAMMA = 2.0
        sample_weights = np.clip((1.0 - oof_p_correct) ** FOCAL_GAMMA, 0.01, 1.0)

        X_sel = train_df[selected]
        final_model = _make_lgbm(**best_params)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            final_model.fit(X_sel, y, sample_weight=sample_weights)

        # ── 10-day horizon model ──────────────────────────────────────────
        # Trained on the same selected features + focal weights but with the
        # 10-day forward return as target.  Adds a longer-horizon perspective
        # that captures multi-day trends not visible in a 5-day window.
        model_10d = None
        y_10d = train_df['target_10d'].astype(int)
        if len(train_df) >= 50:
            try:
                model_10d = _make_lgbm(**best_params)
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    model_10d.fit(X_sel, y_10d, sample_weight=sample_weights)
                logger.info(f"[{symbol}] 10-day horizon model trained on {len(train_df)} rows")
            except Exception as _e:
                logger.debug(f"[{symbol}] 10-day model training failed: {_e}")
                model_10d = None

        # ── Regime-conditional sub-models ─────────────────────────────────
        regime_models: Dict[str, Any] = {}
        regime_labels = _compute_regime_labels(train_df)
        for regime_name in ('calm', 'turbulent'):
            pos_indices = np.where(regime_labels == regime_name)[0]
            if len(pos_indices) < 20:
                logger.debug(
                    f"[{symbol}] Regime '{regime_name}': {len(pos_indices)} rows — skipping sub-model"
                )
                continue
            X_r  = X_sel.iloc[pos_indices]
            y_r  = y.iloc[pos_indices]
            sw_r = sample_weights[pos_indices]
            r_model = _make_lgbm(**best_params)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                r_model.fit(X_r, y_r, sample_weight=sw_r)
            regime_models[regime_name] = r_model
            logger.info(f"[{symbol}] Regime sub-model '{regime_name}' trained on {len(pos_indices)} rows")

        self._regime_models = regime_models

        log_feature_importance(final_model, selected, symbol=symbol, top_n=10)
        self.save_model(final_model, selected, symbol=symbol,
                        best_params=best_params or None, regime_models=regime_models,
                        model_10d=model_10d)

        return final_model, selected

    def _train_model_rf_fallback(self, df, features, symbol=''):
        """RandomForest fallback when LightGBM is not installed."""
        from sklearn.ensemble import RandomForestClassifier

        df = df.copy()
        df['future_return'] = df['close'].shift(-5) / df['close'] - 1
        df['target'] = df['future_return'].apply(
            lambda x: 2 if x > UP_THRESHOLD else (0 if x < DOWN_THRESHOLD else 1)
        )
        train_df = df.dropna(subset=['target'] + features).copy()
        if len(train_df) < 30:
            return None, None

        X, y = train_df[features], train_df['target'].astype(int)
        model = RandomForestClassifier(
            n_estimators=100, max_depth=10, class_weight='balanced',
            random_state=42, n_jobs=-1
        )
        model.fit(X, y)
        self._last_training_accuracy = 0.0
        self._last_samples_used = len(train_df)
        self.save_model(model, features, symbol=symbol)
        return model, features
