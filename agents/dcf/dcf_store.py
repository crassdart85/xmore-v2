"""Persistence layer for DCF valuations and signal emission."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from database import get_connection

logger = logging.getLogger(__name__)


DCF_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dcf_valuations (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  scenario VARCHAR(10),
  intrinsic_per_share NUMERIC(12,2),
  current_price NUMERIC(12,2),
  margin_of_safety NUMERIC(8,4),
  upside_pct NUMERIC(8,2),
  valuation_label VARCHAR(20),
  dcf_confidence VARCHAR(10),
  enterprise_value BIGINT,
  equity_value BIGINT,
  pv_stage1 BIGINT,
  pv_terminal BIGINT,
  terminal_value_pct NUMERIC(5,1),
  wacc NUMERIC(6,4),
  cost_of_equity NUMERIC(6,4),
  beta_used NUMERIC(6,3),
  terminal_growth NUMERIC(6,4),
  net_debt BIGINT,
  years_of_data INT,
  raw_json JSONB,
  UNIQUE (ticker, scenario)
);

CREATE INDEX IF NOT EXISTS idx_dcf_ticker_date ON dcf_valuations (ticker, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_dcf_label ON dcf_valuations (valuation_label, dcf_confidence);
"""


def ensure_dcf_table(conn):
    """Ensure the DCF valuation table exists."""
    cursor = conn.cursor()
    # If using SQLite, adjust SQL types
    if hasattr(conn, 'execute') and conn.__class__.__name__.startswith('Connection'):
        # SQLite path
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dcf_valuations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ticker TEXT NOT NULL,
              computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
              scenario TEXT,
              intrinsic_per_share REAL,
              current_price REAL,
              margin_of_safety REAL,
              upside_pct REAL,
              valuation_label TEXT,
              dcf_confidence TEXT,
              enterprise_value INTEGER,
              equity_value INTEGER,
              pv_stage1 INTEGER,
              pv_terminal INTEGER,
              terminal_value_pct REAL,
              wacc REAL,
              cost_of_equity REAL,
              beta_used REAL,
              terminal_growth REAL,
              net_debt INTEGER,
              years_of_data INTEGER,
              raw_json TEXT,
              UNIQUE(ticker, scenario)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dcf_ticker_date ON dcf_valuations (ticker, computed_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dcf_label ON dcf_valuations (valuation_label, dcf_confidence)")
    else:
        # PostgreSQL path
        cursor.execute(DCF_TABLE_SQL)
    conn.commit()


def store_dcf_results(conn, scenarios: dict, ticker: str):
    """Persist scenario results to the dcf_valuations table."""
    ensure_dcf_table(conn)
    for scenario_name, result in scenarios.items():
        if not result:
            continue
        # Normalize raw JSON for storage
        raw = json.dumps(result)

        if hasattr(conn, 'execute') and conn.__class__.__name__.startswith('Connection'):
            conn.execute("""
                INSERT OR REPLACE INTO dcf_valuations (
                    ticker, scenario, intrinsic_per_share, current_price,
                    margin_of_safety, upside_pct, valuation_label, dcf_confidence,
                    enterprise_value, equity_value, pv_stage1, pv_terminal,
                    terminal_value_pct, wacc, cost_of_equity, beta_used,
                    terminal_growth, net_debt, years_of_data, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, scenario_name,
                result.get("intrinsic_per_share"),
                result.get("current_price"),
                result.get("margin_of_safety"),
                result.get("upside_pct"),
                result.get("valuation_label"),
                result.get("dcf_confidence"),
                result.get("enterprise_value"),
                result.get("equity_value"),
                result.get("pv_stage1"),
                result.get("pv_terminal"),
                result.get("terminal_value_pct"),
                result.get("wacc"),
                result.get("cost_of_equity"),
                result.get("beta_used"),
                result.get("terminal_growth"),
                result.get("net_debt"),
                result.get("years_of_data"),
                raw,
            ))
        else:
            # PostgreSQL path: insert or replace on conflict with (ticker, scenario)
            conn.execute("""
                INSERT INTO dcf_valuations (
                    ticker, scenario, intrinsic_per_share, current_price,
                    margin_of_safety, upside_pct, valuation_label, dcf_confidence,
                    enterprise_value, equity_value, pv_stage1, pv_terminal,
                    terminal_value_pct, wacc, cost_of_equity, beta_used,
                    terminal_growth, net_debt, years_of_data, raw_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, scenario)
                DO UPDATE SET
                  intrinsic_per_share = EXCLUDED.intrinsic_per_share,
                  margin_of_safety    = EXCLUDED.margin_of_safety,
                  valuation_label     = EXCLUDED.valuation_label,
                  dcf_confidence      = EXCLUDED.dcf_confidence,
                  raw_json            = EXCLUDED.raw_json
            """, (
                ticker, scenario_name,
                result.get("intrinsic_per_share"),
                result.get("current_price"),
                result.get("margin_of_safety"),
                result.get("upside_pct"),
                result.get("valuation_label"),
                result.get("dcf_confidence"),
                result.get("enterprise_value"),
                result.get("equity_value"),
                result.get("pv_stage1"),
                result.get("pv_terminal"),
                result.get("terminal_value_pct"),
                result.get("wacc"),
                result.get("cost_of_equity"),
                result.get("beta_used"),
                result.get("terminal_growth"),
                result.get("net_debt"),
                result.get("years_of_data"),
                raw,
            ))
    conn.commit()


def get_latest_composite_dcf(conn, ticker: str) -> dict | None:
    """Fetch latest composite (weighted) DCF result for a ticker."""
    ensure_dcf_table(conn)
    if hasattr(conn, 'execute') and conn.__class__.__name__.startswith('Connection'):
        row = conn.execute(
            "SELECT * FROM dcf_valuations WHERE ticker = ? AND scenario = 'composite' "
            "ORDER BY computed_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return dict(zip(row.keys(), row)) if row else None
    else:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM dcf_valuations WHERE ticker = %s AND scenario = 'composite' "
            "ORDER BY computed_at DESC LIMIT 1",
            (ticker,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
