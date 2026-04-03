"""
Meta-Learner Stacking — Layer 5 of the Consensus Pipeline.

Trains a lightweight LogisticRegression on historical agent outputs to learn
which combinations of agent votes actually predict correct outcomes.  At
inference time it produces a confidence scale factor (0.70 – 1.30) that is
applied to the consensus confidence and Xmore Score before they reach the user.

Design:
  - Features: per-agent signal encoding (UP=1, HOLD=0, DOWN=-1),
              per-agent confidence (0–1), bull/bear scores, agreement ratio,
              turbulent-regime flag.
  - Target: was the final_signal correct? (binary 1/0)
  - Scale formula:  scale = 0.70 + 0.60 × P(correct)
    - At P=0.50 (random) → scale = 1.00  (no adjustment)
    - At P=0.83          → scale = 1.20  (+20% boost)
    - At P=0.17          → scale = 0.80  (−20% penalty)
  - Model cached in models/meta_learner.pkl; retrained automatically when
    ≥100 new labelled rows have accumulated since last training.
  - Non-fatal throughout — returns scale=1.0 on any failure.

Usage (within consensus_engine.run_consensus):
    from engines.meta_learner import MetaLearner
    _meta = MetaLearner()
    adj = _meta.adjust(agent_signals, bull_score, bear_score,
                        agreement_ratio, market_regime, db_conn=conn)
    weighted_confidence *= adj['scale']
    xmore_score = min(100, xmore_score * adj['scale'])
"""

import logging
import os
import warnings
from typing import Dict, List, Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.join('models', 'meta_learner.pkl')
_MIN_TRAIN_ROWS = 50    # Don't train until this many labelled outcomes exist
_RETRAIN_EVERY  = 100   # Retrain when this many new rows have accumulated

_AGENT_NAMES = [
    "ML_RandomForest",
    "MA_Crossover_Agent",
    "RSI_Agent",
    "Volume_Spike_Agent",
]

_SIGNAL_ENC = {"UP": 1.0, "DOWN": -1.0, "HOLD": 0.0, "FLAT": 0.0}


def _encode_features(agent_signals: List[Dict[str, Any]],
                     bull_score: float,
                     bear_score: float,
                     agreement_ratio: float,
                     market_regime: Optional[Dict[str, Any]]) -> Optional[np.ndarray]:
    """
    Build a fixed-length feature vector from consensus inputs.
    Returns None if agent_signals is empty or malformed.
    """
    if not agent_signals:
        return None

    # Per-agent signal + confidence (8 features for 4 agents)
    sig_map: Dict[str, Dict] = {s.get('agent_name', ''): s for s in agent_signals}
    feats = []
    for name in _AGENT_NAMES:
        s = sig_map.get(name, {})
        feats.append(_SIGNAL_ENC.get(s.get('prediction', 'HOLD'), 0.0))
        feats.append(float(s.get('confidence', 50)) / 100.0)

    # Aggregate features (4 features)
    feats.append(float(bull_score) / 100.0)
    feats.append(float(bear_score) / 100.0)
    feats.append(float(agreement_ratio))

    # Regime (1 feature)
    turbulent = 0.0
    if market_regime:
        lbl = market_regime.get('regime_label_en', 'Calm')
        turbulent = 1.0 if lbl in ('Turbulent', 'Crisis') else 0.0
    feats.append(turbulent)

    return np.array(feats, dtype=np.float32).reshape(1, -1)


class MetaLearner:
    """Singleton-safe meta-learner; maintains a per-process in-memory cache."""

    def __init__(self):
        self._model    = None
        self._n_trained = 0    # rows used in last training run
        self._loaded   = False

    # ── Model persistence ─────────────────────────────────────────────────────

    def _load(self) -> bool:
        """Try to load cached model.  Returns True on success."""
        if not os.path.exists(_MODEL_PATH):
            return False
        try:
            import joblib
            data = joblib.load(_MODEL_PATH)
            if isinstance(data, dict) and 'model' in data:
                self._model     = data['model']
                self._n_trained = int(data.get('n_trained', 0))
                logger.info("MetaLearner: loaded model (trained on %d rows)", self._n_trained)
                return True
        except Exception as e:
            logger.debug("MetaLearner: load failed: %s", e)
        return False

    def _save(self, model, n_trained: int):
        try:
            import joblib
            os.makedirs('models', exist_ok=True)
            joblib.dump({'model': model, 'n_trained': n_trained}, _MODEL_PATH)
            logger.info("MetaLearner: saved model (trained on %d rows)", n_trained)
        except Exception as e:
            logger.warning("MetaLearner: save failed: %s", e)

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, conn) -> bool:
        """
        Train on labelled rows from trade_recommendations.
        Features extracted from stored agent_signals_json; target = outcome correct.
        Returns True if training succeeded.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            import json

            cur = conn.cursor()
            is_pg = bool(os.getenv('DATABASE_URL'))
            ph    = "%s" if is_pg else "?"

            cur.execute(f"""
                SELECT final_signal, confidence, agent_signals_json,
                       actual_outcome, bull_score, bear_score
                FROM trade_recommendations
                WHERE actual_outcome IS NOT NULL
                  AND agent_signals_json IS NOT NULL
                  AND (is_live = {'TRUE' if is_pg else '1'} OR is_live IS NULL)
                ORDER BY recommendation_date DESC
                LIMIT 2000
            """)
            rows = cur.fetchall()
            if not rows or len(rows) < _MIN_TRAIN_ROWS:
                logger.debug(
                    "MetaLearner: only %d labelled rows — need %d to train",
                    len(rows) if rows else 0, _MIN_TRAIN_ROWS
                )
                return False

            X_list, y_list = [], []
            for row in rows:
                final_signal, confidence, sigs_json, outcome, bull_s, bear_s = row
                try:
                    agent_sigs = json.loads(sigs_json) if isinstance(sigs_json, str) else (sigs_json or [])
                    regime     = {}
                    bull_score = float(bull_s or 0)
                    bear_score = float(bear_s or 0)
                    # agreement_ratio: approximate from agent_sigs
                    if agent_sigs:
                        majority = max(
                            set(s.get('prediction','HOLD') for s in agent_sigs),
                            key=lambda p: sum(1 for s in agent_sigs if s.get('prediction') == p)
                        )
                        agr = sum(1 for s in agent_sigs if s.get('prediction') == majority) / len(agent_sigs)
                    else:
                        agr = 0.5
                    fv = _encode_features(agent_sigs, bull_score, bear_score, agr, regime)
                    if fv is None:
                        continue
                    # Target: 1 if final_signal matches outcome direction, 0 otherwise
                    correct = int(
                        (final_signal == 'UP'   and outcome == 'UP')   or
                        (final_signal == 'DOWN' and outcome == 'DOWN') or
                        (final_signal == 'HOLD' and outcome in ('HOLD', 'FLAT'))
                    )
                    X_list.append(fv.flatten())
                    y_list.append(correct)
                except Exception:
                    continue

            if len(X_list) < _MIN_TRAIN_ROWS:
                return False

            X = np.array(X_list, dtype=np.float32)
            y = np.array(y_list, dtype=np.int32)

            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                model = LogisticRegression(
                    C=1.0, max_iter=500, class_weight='balanced', random_state=42
                )
                model.fit(X, y)

            self._model     = model
            self._n_trained = len(X_list)
            self._save(model, len(X_list))
            logger.info("MetaLearner: trained on %d rows (accuracy ≈ %.2f%%)",
                        len(X_list), model.score(X, y) * 100)
            return True

        except Exception as e:
            logger.warning("MetaLearner: training failed: %s", e)
            return False

    # ── Inference ─────────────────────────────────────────────────────────────

    def adjust(self,
               agent_signals: List[Dict[str, Any]],
               bull_score: float,
               bear_score: float,
               agreement_ratio: float,
               market_regime: Optional[Dict[str, Any]],
               db_conn=None) -> Dict[str, Any]:
        """
        Return a confidence scale factor for the current consensus.

        scale = 0.70 + 0.60 × P(correct)
          P=0.50 → scale 1.00 (baseline)
          P=0.83 → scale 1.20 (validated signal → boost)
          P=0.17 → scale 0.80 (anti-predictive pattern → penalty)

        Always returns {'scale': float, 'p_correct': float, 'source': str}.
        Falls back to scale=1.0 on any failure.
        """
        neutral = {'scale': 1.0, 'p_correct': 0.5, 'source': 'fallback'}

        try:
            # Lazy load / train
            if not self._loaded:
                self._loaded = True
                if not self._load() and db_conn is not None:
                    self.train(db_conn)

            # Trigger periodic retrain when enough new rows exist
            if db_conn is not None and self._model is not None:
                try:
                    cur = db_conn.cursor()
                    is_pg = bool(os.getenv('DATABASE_URL'))
                    cur.execute("""
                        SELECT COUNT(*) FROM trade_recommendations
                        WHERE actual_outcome IS NOT NULL
                          AND agent_signals_json IS NOT NULL
                    """)
                    total = int((cur.fetchone() or [0])[0])
                    if total >= self._n_trained + _RETRAIN_EVERY:
                        self.train(db_conn)
                except Exception:
                    pass

            if self._model is None:
                return neutral

            fv = _encode_features(agent_signals, bull_score, bear_score,
                                  agreement_ratio, market_regime)
            if fv is None:
                return neutral

            proba = self._model.predict_proba(fv)[0]
            classes = list(self._model.classes_)
            p_correct = float(proba[classes.index(1)]) if 1 in classes else 0.5

            scale = round(0.70 + 0.60 * p_correct, 3)
            return {'scale': scale, 'p_correct': round(p_correct, 3), 'source': 'meta_learner'}

        except Exception as e:
            logger.debug("MetaLearner.adjust failed: %s", e)
            return neutral


# Module-level singleton — shared across all calls within one process
_meta_learner_instance: Optional[MetaLearner] = None


def get_meta_learner() -> MetaLearner:
    global _meta_learner_instance
    if _meta_learner_instance is None:
        _meta_learner_instance = MetaLearner()
    return _meta_learner_instance
