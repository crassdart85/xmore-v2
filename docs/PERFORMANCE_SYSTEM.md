# 📊 Performance Tracking & Validation System

## Document Control

| Field | Details |
|-------|---------|
| **Version** | 1.0 |
| **Date** | February 12, 2026 |
| **Status** | Implemented |

---

## 1. Overview

The Xmore Performance System provides **investor-grade, auditable** tracking of all AI predictions. It enforces immutability of core prediction data, calculates professional financial metrics (Sharpe ratio, alpha, drawdown), compares performance against the EGX30 benchmark, and exposes public API endpoints for transparency.

### Design Principles
- **Immutability**: Predictions cannot be modified after creation (enforced at DB level via PostgreSQL triggers)
- **Audit Trail**: All outcome field changes are logged in `prediction_audit_log`
- **Live Only**: Public metrics use only `is_live = TRUE` data (no backtests)
- **Reproducibility**: All calculations depend solely on database data
- **Transparency**: All endpoints are public (no auth required)

---

## 2. Database Schema

### 2.1 New Tables

| Table | Purpose |
|-------|---------|
| `prediction_audit_log` | Logs every modification to outcome fields on trade_recommendations |
| `agent_performance_daily` | Stores daily snapshots of per-agent rolling accuracy (30d, 90d) |

### 2.2 Altered Columns (trade_recommendations)

| Column | Type | Purpose |
|--------|------|---------|
| `benchmark_1d_return` | REAL | EGX30 1-day return on the same date |
| `alpha_1d` | REAL | Xmore return minus benchmark return (1-day) |
| `benchmark_5d_return` | REAL | EGX30 5-day return |
| `alpha_5d` | REAL | Alpha for 5-day window |
| `is_live` | BOOLEAN | TRUE for live predictions, FALSE for backtests |

### 2.3 Altered Columns (user_positions)

| Column | Type | Purpose |
|--------|------|---------|
| `benchmark_return_pct` | REAL | EGX30 return over the same holding period |
| `alpha_pct` | REAL | Position return minus benchmark return |

### 2.4 PostgreSQL-Only Features

| Feature | Details |
|---------|---------|
| **Immutability Triggers** | `prevent_consensus_mutation` and `prevent_trade_mutation` prevent changes to core fields |
| **Audit Trigger** | `log_trade_outcome_changes` logs changes to outcome fields |
| **Materialized View** | `mv_performance_global` for fast global stats (refreshed daily) |
| **Refresh Function** | `refresh_performance_views()` — called by evaluation engine |

### 2.5 Migration File

- `web-ui/migrations/007_performance_benchmark.sql` — Full migration script

---

## 3. Python Engines

### 3.1 engines/evaluate_performance.py

**Replaces**: `engines/evaluate_trades.py` (legacy)

**Entry Point**: `run_evaluation(pipeline_run_id=None)`

**Pipeline Step**: Step 8 (runs after briefing generation in `run_agents.py`)

**Functions**:

| Function | Purpose |
|----------|---------|
| `resolve_1day_outcomes()` | Fills `actual_next_day_return`, `was_correct`, `benchmark_1d_return`, `alpha_1d` |
| `resolve_5day_outcomes()` | Fills `actual_5day_return`, `benchmark_5d_return`, `alpha_5d` |
| `resolve_position_benchmarks()` | Calculates benchmark/alpha for closed user_positions |
| `update_agent_accuracy_snapshot()` | Inserts daily agent accuracy into `agent_performance_daily` (PG only) |
| `refresh_performance_views()` | Refreshes `mv_performance_global` materialized view (PG only) |
| `get_benchmark_return(date, window)` | Fetches EGX30 return for a date + window combination |

**Helpers**:
- `get_connection()` — from `database.py`
- `_adapt_sql(sql)` — from `database.py`, converts `?` to `%s` for PostgreSQL
- `_date_interval(days)` — SQL syntax for date arithmetic (PG vs SQLite)

### 3.2 engines/performance_metrics.py

**Pure computation module** — no side effects.

| Function | Returns |
|----------|---------|
| `get_performance_summary(days, live_only)` | Dict with total_predictions, win_rate, avg_alpha_1d, sharpe_ratio, sortino_ratio, max_drawdown, profit_factor, etc. |
| `get_rolling_metrics(windows)` | Dict keyed by window ("30d", "90d"), with trades/win_rate/alpha per window |
| `get_agent_comparison()` | List of agent dicts from `agent_performance_daily` |
| `get_stock_performance(days)` | List of per-stock performance dicts |
| `get_equity_curve(days)` | List of {date, xmore, egx30, alpha} points for charting |

---

## 4. API Endpoints

**Base URL**: `/api/performance-v2/`

**Authentication**: None (public for transparency)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/summary` | Overall performance stats + rolling metrics |
| GET | `/by-agent` | Per-agent accuracy comparison (latest snapshot) |
| GET | `/by-stock?days=N` | Per-stock performance breakdown |
| GET | `/equity-curve?days=N` | Cumulative return series for charting |
| GET | `/predictions/open` | Currently open (unresolved) predictions |
| GET | `/predictions/history?page=N&limit=N` | Auditable prediction history, paginated |
| GET | `/audit?limit=N` | Prediction modification audit trail |

**File**: `web-ui/routes/performance.js`

**Server registration** (in `web-ui/server.js`):
```javascript
const { router: performanceRouter, attachDb: attachPerformanceDb } = require('./routes/performance');
attachPerformanceDb(db, isPostgres);
app.use('/api/performance-v2', performanceRouter);
```

---

## 5. Frontend Dashboard

### 5.1 Files

| File | Purpose |
|------|---------|
| `web-ui/public/performance-dashboard.js` | All dashboard logic — builds sections dynamically, renders canvas chart, handles pagination and modals |
| `web-ui/public/performance-dashboard.css` | Premium styling with dark/light theme, RTL, responsive grid |

### 5.2 Dashboard Sections (rendered in order)

1. **Header** — Title with gradient, disclaimer banner
2. **Key Metrics Grid** — 4 cards: Trades, Win Rate, Avg Alpha, Beat Market %
3. **Equity Curve** — Canvas chart with period selector (30d/60d/90d/180d)
4. **Agent Accuracy Table** — Agent name, 30d win%, 90d win%, signals, avg confidence
5. **Best & Worst Stocks** — Chip components showing top/bottom alpha performers
6. **Recent Predictions** — Paginated table with "Show More" and "View Audit Log" buttons
7. **Rolling Windows** — 30d/90d comparison table
8. **Integrity Section** — Immutability, audit trail, live-only, minimum threshold notices
9. **Disclaimer** — Legal disclaimer in both languages

### 5.3 Integration Points

- **index.html**: CSS link in `<head>`, JS script before `</body>`, tab content replaced with `<div id="perfDashboard">`
- **app.js**: `initTabs()` function calls `loadPerformanceDashboard()` when performance tab is clicked

### 5.4 Bilingual Support

The dashboard has its own `PERF_TRANSLATIONS` object with `en` and `ar` keys, using the `pt(key)` function. It reads the global `currentLang` variable from `app.js`.

---

## 6. Pipeline Integration

### 6.1 Execution Order (run_agents.py)

```
1. Fetch price data + sentiment
2. Run 4 signal agents (Layer 1)
3. Run Consensus Engine (Layers 2 & 3)
4. Store predictions + consensus
5. Generate trade recommendations
6. Open/close positions
7. Generate daily briefing
8. ★ NEW: Run performance evaluation (evaluate_performance.py)
```

### 6.2 Briefing Integration

The `engines/briefing_generator.py` now includes a `get_briefing_performance_snippet()` function that fetches 30-day rolling metrics and adds a `track_record` field to the daily briefing JSON:

```json
{
  "track_record": {
    "available": true,
    "period": "30d",
    "total_trades": 47,
    "win_rate": 58.2,
    "avg_alpha": 0.3,
    "message_en": "30-day record: 58.2% win rate, +0.3% avg alpha.",
    "message_ar": "سجل 30 يوم: نسبة فوز 58.2%، ألفا متوسط +0.3%."
  }
}
```

---

## 5. Discounted Cash Flow (DCF) Valuation Engine

The DCF engine runs once per week (Sunday) and generates a **composite fair value** for each EGX Top-50 company.
It outputs a signal that is used as an **additional agent input** for the consensus engine, providing a fundamental valuation layer on top of technical agents.

### 5.1 What it produces

Each DCF run stores a record in `dcf_valuations` with:
- **intrinsic_per_share** (EGP) — fair value from the model
- **current_price** (EGP)
- **margin_of_safety** (discount/premium vs price)
- **valuation_label** (`DEEP_VALUE`, `UNDERVALUED`, `FAIR`, `OVERVALUED`, `SPECULATIVE`)
- **dcf_confidence** (`LOW`, `MEDIUM`, `HIGH`)
- **upside_pct**, **wacc**, **terminal_growth**, and other valuation components

### 5.2 Database Schema

The `dcf_valuations` table stores all DCF results:

```sql
CREATE TABLE dcf_valuations (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  scenario VARCHAR(10),        -- 'bull', 'base', 'bear', 'composite'
  intrinsic_per_share NUMERIC(12,2),
  current_price NUMERIC(12,2),
  margin_of_safety NUMERIC(8,4),
  upside_pct NUMERIC(8,2),
  valuation_label VARCHAR(20),
  dcf_confidence VARCHAR(10),
  wacc NUMERIC(6,4),
  cost_of_equity NUMERIC(6,4),
  terminal_growth NUMERIC(6,4),
  net_debt BIGINT,
  raw_json JSONB,
  UNIQUE (ticker, scenario)
);
```

**Indexes:** `idx_dcf_ticker_date`, `idx_dcf_label` for fast queries on ticker/date and valuation category.

**Note:** Each INSERT replaces the previous record for the same `(ticker, scenario)` pair, ensuring the latest valuation is always available.

### 5.3 Code Modules

The DCF engine is implemented in the `agents/dcf/` directory:

- **[dcf_config.py](../../agents/dcf/dcf_config.py)** — macro parameters (risk-free rate, market premium, Egypt-specific adjustments)
- **[data_collector.py](../../agents/dcf/data_collector.py)** — fetches financial statements from yfinance
- **[fcf_projector.py](../../agents/dcf/fcf_projector.py)** — projects 5-year quarterly free cash flows
- **[wacc_calculator.py](../../agents/dcf/wacc_calculator.py)** — computes WACC with Egypt-calibrated parameters
- **[dcf_engine.py](../../agents/dcf/dcf_engine.py)** — two-stage DCF model (explicit period + terminal/Gordon growth)
- **[scenario_runner.py](../../agents/dcf/scenario_runner.py)** — runs bull/base/bear scenar ios and composites the results
- **[dcf_store.py](../../agents/dcf/dcf_store.py)** — persists results to database, emits signals
- **[run_dcf.py](../../agents/dcf/run_dcf.py)** — weekly orchestrator; called from `run_agents.py` on Sundays
- **[dcf_agent.py](../../agents/dcf/dcf_agent.py)** — consensus agent integrating DCF signal into multi-agent vote

### 5.4 How it integrates into Consensus

- The `DCF_Valuation_Agent` reads the latest composite DCF (`scenario='composite'`) for each ticker
- It emits a signal (UP/DOWN/HOLD) and confidence (mapped from DCF confidence) into the consensus pipeline
- This allows the consensus engine to shift weight when the model indicates a deep discount or overvaluation

### 5.5 Running DCF Locally

To run the DCF pipeline on demand (normally runs automatically on Sundays):

```bash
# Activate virtual environment
& .\.venv\Scripts\Activate.ps1

# Run DCF for top 50 EGX companies
python -m agents.dcf.run_dcf

# Or run full pipeline including DCF
python run_agents.py

# Or run just the consensus engine (which will use latest DCF signals)
python -m agents.consensus_engine
```

**Expected Output:**
- Console logs showing data fetching, projection, valuation, and storage progress for each ticker
- New rows inserted into `dcf_valuations` with timestamp, scenario, and fair value estimates
- Signal emission log entries showing UP/HOLD/DOWN signals and confidence levels being fed into consensus

**Debugging:**
- Check `logs/` directory for detailed agent logs
- Query `dcf_valuations` table to inspect stored results:
  ```sql
  SELECT ticker, scenario, intrinsic_per_share, current_price, valuation_label
    FROM dcf_valuations
   WHERE ticker = 'EGID' AND DATE(computed_at) = CURRENT_DATE
   ORDER BY scenario DESC;
  ```

### 5.6 Pipeline and Scheduling

- The DCF pipeline is triggered weekly (Sunday) via `run_agents.py` and the `agents/dcf/run_dcf.py` orchestrator
- The results are persisted in `dcf_valuations` and exposed to any downstream consumers (dashboard, news, simulation)

---

## 7. Cross-Database Compatibility

| Feature | PostgreSQL | SQLite |
|---------|-----------|--------|
| Immutability triggers | ✅ | ❌ Skipped |
| Audit triggers | ✅ | ❌ Skipped |
| Materialized view | ✅ | ❌ Computed on-the-fly |
| Boolean syntax | `TRUE`/`FALSE` | `1`/`0` |
| Date intervals | `CURRENT_DATE - N` | `date('now', '-N days')` |
| Placeholders | `$1, $2` | `?, ?` |
| FILTER clause | ✅ | ❌ Uses CASE WHEN |
| ALTER TABLE | ✅ | ✅ (wrapped in try/except) |

---

## 8. Minimum Trade Threshold

The system enforces a **100-trade minimum** for statistical credibility. Until this threshold is met:
- A warning banner is shown on the dashboard
- The integrity section displays progress (e.g., "47/100 trades resolved")
- The `meets_minimum` field in the API response is `false`

---

*Last Updated: February 12, 2026*
