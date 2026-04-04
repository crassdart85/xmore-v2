"""
Dynamic Agent Weighting — softmax-based weight computation with audit logging.

Computes weights from recent directional accuracy, logs every weight update
to `agent_weights_log` for transparency and post-hoc analysis.

The softmax ensures weights sum to 1 and punishes poor performers without
fully zeroing them out — preserving ensemble diversity.
"""

import os
import math
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

# Floor: no agent gets less than 5% weight
MIN_WEIGHT = 0.05
# Minimum evaluated predictions before adjusting (below → mean weight)
MIN_PREDICTIONS = 5
# Lookback window in days
DEFAULT_LOOKBACK_DAYS = 30
# Softmax temperature — higher = more uniform, lower = more peaked
SOFTMAX_TEMPERATURE = 2.0


def _ph(n: int) -> str:
    return f'${n}' if DATABASE_URL else '?'


def _ensure_weights_log_table(cursor):
    """Create agent_weights_log table if it doesn't exist."""
    if DATABASE_URL:
        auto_id = 'SERIAL PRIMARY KEY'
    else:
        auto_id = 'INTEGER PRIMARY KEY AUTOINCREMENT'

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS agent_weights_log (
            id {auto_id},
            agent_name TEXT NOT NULL,
            weight REAL NOT NULL,
            accuracy REAL,
            sample_size INTEGER NOT NULL DEFAULT 0,
            computed_at TIMESTAMP NOT NULL DEFAULT {'NOW()' if DATABASE_URL else "datetime('now')"}
        )
    """)


def _softmax(scores: dict, temperature: float = SOFTMAX_TEMPERATURE) -> dict:
    """Apply softmax to a dict of {name: score} → {name: probability}."""
    if not scores:
        return {}
    # Subtract max for numerical stability
    max_val = max(scores.values())
    exp_scores = {}
    for k, v in scores.items():
        exp_scores[k] = math.exp((v - max_val) / temperature)
    total = sum(exp_scores.values())
    if total == 0:
        n = len(scores)
        return {k: 1.0 / n for k in scores}
    return {k: v / total for k, v in exp_scores.items()}


def _apply_floor(weights: dict, floor: float = MIN_WEIGHT) -> dict:
    """Apply minimum weight floor and renormalize."""
    floored = {k: max(floor, v) for k, v in weights.items()}
    total = sum(floored.values())
    if total == 0:
        n = len(floored)
        return {k: 1.0 / n for k in floored}
    return {k: round(v / total, 4) for k, v in floored.items()}


def compute_agent_weights(db_conn, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict:
    """
    Compute dynamic weights for each agent based on recent directional accuracy.

    Algorithm:
    1. Query last `lookback_days` of evaluated predictions per agent
    2. Compute accuracy_score = correct / total per agent
    3. Apply softmax to accuracy scores
    4. Floor each weight at 5%
    5. Agents with < MIN_PREDICTIONS get mean weight

    Returns: {agent_name: weight} where weights sum to ~1.0
    """
    from agents.consensus_engine import AGENT_WEIGHTS

    base_agents = list(AGENT_WEIGHTS.keys())
    n_agents = len(base_agents)
    mean_weight = 1.0 / n_agents if n_agents > 0 else 0.25

    try:
        cursor = db_conn.cursor()

        if DATABASE_URL:
            cutoff_expr = f"NOW() - INTERVAL '{lookback_days} days'"
            query = f"""
                SELECT p.agent_name,
                       COUNT(*) as total,
                       SUM(CASE WHEN e.ok = TRUE THEN 1 ELSE 0 END) as correct
                FROM predictions p
                JOIN evaluations e ON e.prediction_id = p.id
                WHERE p.prediction_date >= {cutoff_expr}
                  AND p.agent_name != 'Consensus'
                GROUP BY p.agent_name
                HAVING COUNT(*) >= 1
            """
        else:
            cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
            query = f"""
                SELECT p.agent_name,
                       COUNT(*) as total,
                       SUM(CASE WHEN e.ok = 1 THEN 1 ELSE 0 END) as correct
                FROM predictions p
                JOIN evaluations e ON e.prediction_id = p.id
                WHERE p.prediction_date >= ?
                  AND p.agent_name != 'Consensus'
                GROUP BY p.agent_name
                HAVING COUNT(*) >= 1
            """

        if DATABASE_URL:
            cursor.execute(query)
        else:
            cursor.execute(query, (cutoff,))

        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall() or []

        # Build accuracy scores
        accuracy_scores = {}
        sample_sizes = {}
        for row in rows:
            rec = row if isinstance(row, dict) else dict(zip(cols, row))
            agent = rec['agent_name']
            total = int(rec['total'] or 0)
            correct = int(rec['correct'] or 0)
            accuracy = (correct / total * 100) if total > 0 else 50.0
            accuracy_scores[agent] = accuracy
            sample_sizes[agent] = total

        # Ensure all known agents are present
        for agent in base_agents:
            if agent not in accuracy_scores:
                accuracy_scores[agent] = 50.0  # neutral
                sample_sizes[agent] = 0

        # Apply softmax
        weights = _softmax(accuracy_scores)

        # Agents with insufficient data get mean weight
        for agent in weights:
            if sample_sizes.get(agent, 0) < MIN_PREDICTIONS:
                weights[agent] = mean_weight

        # Apply floor and renormalize
        weights = _apply_floor(weights)

        # Log to agent_weights_log
        _log_weights(cursor, weights, accuracy_scores, sample_sizes)

        try:
            db_conn.commit()
        except Exception:
            pass

        logger.info(f"Softmax agent weights (lookback={lookback_days}d): {weights}")
        return weights

    except Exception as e:
        logger.warning(f"compute_agent_weights failed: {e}")
        return {agent: round(1.0 / n_agents, 4) for agent in base_agents}


def _log_weights(cursor, weights: dict, accuracy_scores: dict, sample_sizes: dict):
    """Log computed weights to agent_weights_log for auditability."""
    try:
        _ensure_weights_log_table(cursor)
        for agent, weight in weights.items():
            accuracy = accuracy_scores.get(agent)
            sample_size = sample_sizes.get(agent, 0)
            if DATABASE_URL:
                cursor.execute("""
                    INSERT INTO agent_weights_log (agent_name, weight, accuracy, sample_size, computed_at)
                    VALUES ($1, $2, $3, $4, NOW())
                """, (agent, weight, accuracy, sample_size))
            else:
                cursor.execute("""
                    INSERT INTO agent_weights_log (agent_name, weight, accuracy, sample_size, computed_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (agent, weight, accuracy, sample_size))
    except Exception as e:
        logger.warning(f"Failed to log agent weights: {e}")


def weighted_consensus(signals: dict, weights: dict) -> tuple:
    """
    Compute consensus signal with confidence score.

    Args:
        signals: {agent_name: 'BUY' | 'SELL' | 'HOLD' | 'UP' | 'DOWN'}
        weights: {agent_name: weight} from compute_agent_weights()

    Returns: (consensus_signal, confidence_score)
        confidence_score = winning_weight_sum / total_weight
    """
    if not signals:
        return 'HOLD', 0.0

    # Normalize signal names
    norm_map = {'BUY': 'UP', 'SELL': 'DOWN', 'FLAT': 'HOLD'}
    direction_weights = {'UP': 0.0, 'DOWN': 0.0, 'HOLD': 0.0}
    total_weight = 0.0

    for agent, signal in signals.items():
        w = weights.get(agent, 0.20)
        normalized = norm_map.get(signal, signal)
        if normalized in direction_weights:
            direction_weights[normalized] += w
        else:
            direction_weights['HOLD'] += w
        total_weight += w

    if total_weight == 0:
        return 'HOLD', 0.0

    best_direction = max(direction_weights, key=direction_weights.get)
    confidence_score = direction_weights[best_direction] / total_weight

    return best_direction, round(confidence_score, 4)
