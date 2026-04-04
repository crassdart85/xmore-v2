-- Migration 013: Dynamic Agent Weights
-- Stores per-agent softmax weights computed from recent directional accuracy.
-- Used for auditing how agent influence evolves over time.

CREATE TABLE IF NOT EXISTS agent_weights_log (
    id SERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    weight REAL NOT NULL,
    accuracy REAL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    computed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_weights_log_date ON agent_weights_log(computed_at DESC);

-- Add confidence_score to predictions table (consensus confidence)
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS confidence_score REAL;
