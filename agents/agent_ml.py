"""
ML LightGBM Agent

Uses LightGBM gradient-boosted trees with 40+ TA-Lib technical indicators.
Implements walk-forward validation (TimeSeriesSplit) to prevent look-ahead bias.
Applies feature selection (top-20 by gain importance) after the WFV pass to
reduce noise from the high-dimensional feature space.
Uses class_weight='balanced' to handle the FLAT class imbalance inherent in
EGX daily price data.
"""

import pandas as pd
import numpy as np
import joblib
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from lightgbm import LGBMClassifier
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False
    from sklearn.ensemble import RandomForestClassifier

from sklearn.model_selection import TimeSeriesSplit

from agents.agent_base import BaseAgent, AgentSignal
from features import add_technical_indicators, add_sentiment_features, add_macro_features, get_feature_columns, log_feature_importance
from database import get_connection

logger = logging.getLogger(__name__)

MODEL_DIR = 'models'
MODEL_PATH = os.path.join(MODEL_DIR, 'stock_predictor.pkl')
MODEL_MAX_AGE_DAYS = 7   # Force retrain if saved model is older than this

# Prediction return thresholds
UP_THRESHOLD = 0.005    # +0.5% = UP
DOWN_THRESHOLD = -0.005  # -0.5% = DOWN

# Feature selection
_TOP_N_FEATURES = 20   # Keep top-N by gain importance after WFV
_MIN_FEATURES = 10     # Never drop below this many features


def _select_top_features(model, features: list, top_n: int = _TOP_N_FEATURES) -> list:
    """
    Return the top_n features ranked by LightGBM gain importance.

    Gain importance (total information gain contributed by a feature across all
    splits) is more informative than the default 'split' count for feature
    selection because it reflects contribution to prediction quality, not
    just frequency of use.

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


def _make_lgbm(**kwargs):
    """
    Build a LGBMClassifier with sane defaults for EGX financial data.

    Key choices:
      class_weight='balanced'  — corrects UP/DOWN minority vs FLAT majority
      learning_rate=0.05       — conservative; prevents overfit on small datasets
      num_leaves=31            — default; avoids deep trees on ~100–300 row sets
      min_child_samples=10     — minimum leaf population; regularises thin leaves
      subsample/colsample_bytree=0.8 — row/column sampling per tree (bagging)
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


class MLAgent(BaseAgent):
    def __init__(self):
        super().__init__("ML_RandomForest")
        self.model = None
        self.feature_names = None
        self._last_probs = None
        self._last_top_features = None
        self._last_training_accuracy = None
        self._last_samples_used = None
        self.load_model()

    def load_model(self):
        """
        Load pre-trained model if it exists and is not stale.
        Models older than MODEL_MAX_AGE_DAYS are discarded so the pipeline
        retrains on the next run, picking up recent price patterns.
        """
        if os.path.exists(MODEL_PATH):
            try:
                data = joblib.load(MODEL_PATH)
                if isinstance(data, dict):
                    trained_at = data.get('trained_at')
                    if trained_at:
                        age_days = (datetime.now() - datetime.fromisoformat(trained_at)).days
                        if age_days > MODEL_MAX_AGE_DAYS:
                            logger.info(
                                f"Model is {age_days}d old (> {MODEL_MAX_AGE_DAYS}d max) — "
                                f"will retrain on next predict()"
                            )
                            return  # Leave self.model = None → triggers retrain in predict()
                    self.model = data.get('model')
                    self.feature_names = data.get('feature_names', get_feature_columns())
                else:
                    # Legacy pickle without metadata — treat as stale, force retrain
                    logger.info("Legacy model format (no trained_at) — will retrain")
                    return
                logger.info(f"Model loaded from {MODEL_PATH} (trained {trained_at})")
            except Exception as e:
                logger.error(f"Error loading model: {e}")
        else:
            logger.warning(f"Model not found at {MODEL_PATH}. Will train on-the-fly.")

    def save_model(self, model, feature_names):
        """Save trained model with feature names and training timestamp."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        data = {
            'model': model,
            'feature_names': feature_names,
            'trained_at': datetime.now().isoformat(),
        }
        joblib.dump(data, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")

    def predict(self, price_df, sentiment: Optional[Dict[str, Any]] = None):
        """
        Predict using LightGBM model.
        Expects price_df to have full history for indicator calculation.

        If no pre-trained model exists, trains on available data using
        walk-forward validation (TimeSeriesSplit) then feature selection.
        """
        symbol = price_df.iloc[0]['symbol'] if 'symbol' in price_df.columns else 'UNKNOWN'

        df = price_df.copy()

        news_df = pd.DataFrame()
        macro_df = pd.DataFrame()
        if symbol and symbol != 'UNKNOWN':
            try:
                with get_connection() as conn:
                    news_df = pd.read_sql(
                        f"SELECT date, sentiment_score FROM news WHERE symbol='{symbol}'",
                        conn
                    )
            except Exception:
                pass

        # Fetch macro context (Brent, USD/EGP, EM) for cross-market features
        try:
            with get_connection() as conn:
                macro_df = pd.read_sql("""
                    SELECT date,
                        MAX(CASE WHEN symbol='MACRO_BRENT'  THEN close END) AS brent_close,
                        MAX(CASE WHEN symbol='MACRO_USDEGP' THEN close END) AS usdegp_close,
                        MAX(CASE WHEN symbol='MACRO_EEM'    THEN close END) AS eem_close
                    FROM prices
                    WHERE symbol IN ('MACRO_BRENT', 'MACRO_USDEGP', 'MACRO_EEM')
                    GROUP BY date
                    ORDER BY date
                """, conn)
        except Exception:
            pass

        df = add_technical_indicators(df)
        df = add_sentiment_features(df, news_df)
        df = add_macro_features(df, macro_df)

        all_features = get_feature_columns()
        available_features = [f for f in all_features if f in df.columns and not df[f].isna().all()]

        if len(available_features) < 5:
            logger.warning(f"[{symbol}] Only {len(available_features)} features available, using HOLD")
            return "HOLD"

        if self.model is None:
            self.model, self.feature_names = self._train_model(df, available_features, symbol)

        if self.model is None:
            return "HOLD"

        features = [f for f in self.feature_names if f in df.columns]
        if len(features) < len(self.feature_names) * 0.5:
            logger.warning(f"[{symbol}] Too many features missing, retraining...")
            self.model, self.feature_names = self._train_model(df, available_features, symbol)
            features = available_features

        if self.model is None:
            return "HOLD"

        last_row = df.iloc[[-1]].copy()

        # LightGBM handles NaN natively; fill as safety net for edge cases
        for feat in features:
            if feat in last_row.columns and last_row[feat].isna().any():
                last_row[feat] = 0

        try:
            X = last_row[features]
            prediction = self.model.predict(X)[0]

            probs = self.model.predict_proba(X)[0]
            confidence = max(probs)

            # Store for predict_signal
            classes = self.model.classes_
            self._last_probs = {}
            mapping_inv = {0: "DOWN", 1: "FLAT", 2: "UP"}
            for i, cls in enumerate(classes):
                label = mapping_inv.get(cls, str(cls))
                self._last_probs[label] = round(float(probs[i]), 3)

            # Get top features by gain importance
            try:
                if hasattr(self.model, 'booster_'):
                    importances = self.model.booster_.feature_importance(importance_type='gain')
                else:
                    importances = self.model.feature_importances_
                feat_importance = sorted(
                    zip(features, importances),
                    key=lambda x: x[1], reverse=True
                )[:5]
                self._last_top_features = []
                for fname, fimp in feat_importance:
                    val = float(last_row[fname].iloc[0]) if fname in last_row.columns else 0
                    self._last_top_features.append({
                        "name": fname,
                        "importance": round(float(fimp), 4),
                        "value": round(val, 4)
                    })
            except Exception:
                pass

            mapping = {0: "DOWN", 1: "FLAT", 2: "UP"}
            result = mapping.get(prediction, "HOLD")

            logger.info(f"[{symbol}] Prediction: {result} (confidence: {confidence:.2f})")
            return result

        except Exception as e:
            logger.error(f"[{symbol}] Prediction error: {e}")
            return "HOLD"

    def predict_signal(self, data: pd.DataFrame, symbol: str = "",
                       sentiment: Optional[Dict[str, Any]] = None) -> dict:
        """
        Generate structured prediction with ML reasoning data.

        Returns dict with class probabilities, top features, and training accuracy.
        """
        # Run predict first to populate internal state
        prediction = self.predict(data, sentiment)

        # Build probabilities dict
        class_probs = self._last_probs or {"UP": 0.33, "DOWN": 0.33, "FLAT": 0.34}
        top_features = self._last_top_features or []

        # Confidence from max probability
        confidence = max(class_probs.values()) * 100 if class_probs else 50.0

        reasoning = {
            "class_probabilities": class_probs,
            "top_features": top_features,
            "training_accuracy": round(self._last_training_accuracy or 0, 3),
            "samples_used": self._last_samples_used or 0
        }

        return AgentSignal(
            agent_name=self.name, symbol=symbol,
            prediction=prediction, confidence=round(confidence, 1),
            reasoning=reasoning
        ).to_dict()

    def _train_model(self, df, features, symbol=''):
        """
        Train LightGBM with walk-forward validation (TimeSeriesSplit),
        then select top features by gain importance and retrain final model.

        Two-pass training:
          Pass 1  WFV across n_splits folds — picks best fold model and
                  measures average OOS accuracy.
          Pass 2  Select top-_TOP_N_FEATURES by gain from best fold model,
                  retrain on ALL available data with selected features.
                  This final model is what gets saved and used for inference.
        """
        if not LGBM_AVAILABLE:
            logger.warning("LightGBM not installed — falling back to RandomForest")
            return self._train_model_rf_fallback(df, features, symbol)

        df = df.copy()
        df['future_return'] = df['close'].shift(-5) / df['close'] - 1
        df['target'] = df['future_return'].apply(
            lambda x: 2 if x > UP_THRESHOLD else (0 if x < DOWN_THRESHOLD else 1)
        )

        train_df = df.dropna(subset=['target'] + features).copy()

        if len(train_df) < 30:
            logger.warning(f"[{symbol}] Not enough data to train ({len(train_df)} rows)")
            return None, None

        X = train_df[features]
        y = train_df['target'].astype(int)

        n_splits = min(5, len(X) // 10)
        if n_splits < 2:
            n_splits = 2

        tscv = TimeSeriesSplit(n_splits=n_splits)
        scores = []
        best_model = None
        best_score = 0

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            model = _make_lgbm()
            model.fit(X_train, y_train)
            score = model.score(X_test, y_test)
            scores.append(score)

            if score > best_score:
                best_score = score
                best_model = model

        avg_score = np.mean(scores)
        self._last_training_accuracy = avg_score
        self._last_samples_used = len(train_df)
        logger.info(
            f"[{symbol}] LightGBM WFV: avg accuracy = {avg_score:.3f} "
            f"(splits={n_splits}, class_weight=balanced)"
        )

        if best_model is None:
            return None, None

        # ── Pass 2: Feature selection + final retrain ──────────────────────────
        selected = _select_top_features(best_model, features, top_n=_TOP_N_FEATURES)
        if len(selected) < len(features):
            logger.info(
                f"[{symbol}] Feature selection: {len(features)} → {len(selected)} features"
            )

        X_sel = train_df[selected]
        final_model = _make_lgbm()
        final_model.fit(X_sel, y)

        log_feature_importance(final_model, selected, symbol=symbol, top_n=10)
        self.save_model(final_model, selected)

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

        X = train_df[features]
        y = train_df['target'].astype(int)
        model = RandomForestClassifier(
            n_estimators=100, max_depth=10, class_weight='balanced',
            random_state=42, n_jobs=-1
        )
        model.fit(X, y)
        self._last_training_accuracy = 0.0
        self._last_samples_used = len(train_df)
        self.save_model(model, features)
        return model, features
