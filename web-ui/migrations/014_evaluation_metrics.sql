-- Migration 014: Calibrated Evaluation Metrics
-- Adds magnitude-weighted score, Brier calibration, signal strength, and actual return
-- to the evaluations table for multi-metric performance analysis.

ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS magnitude_score REAL;
ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS calibration_score REAL;
ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS signal_strength REAL;
ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS actual_return REAL;
