-- Migration 015: Job Locks
-- Advisory locking table to prevent concurrent pipeline steps
-- (e.g. evaluate.py reading prices while collect_data.py is still writing)

CREATE TABLE IF NOT EXISTS job_locks (
    job_name TEXT PRIMARY KEY,
    locked_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);
