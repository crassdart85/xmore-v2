# Business Requirements Document (BRD)
## Xmore — AI Stock Intelligence Platform for the Egyptian Exchange

| Field | Detail |
|---|---|
| **Document version** | 1.2 |
| **Date** | March 2026 |
| **Status** | Live / In Production |
| **Platform URL** | xmore-project.onrender.com |
| **Repository** | github.com/crassdart85/xmore-v2 |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context & Objectives](#2-business-context--objectives)
3. [Stakeholders](#3-stakeholders)
4. [Scope](#4-scope)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [System Architecture](#7-system-architecture)
8. [Data Requirements](#8-data-requirements)
9. [Integrations & External Dependencies](#9-integrations--external-dependencies)
10. [Automated Pipeline](#10-automated-pipeline)
11. [Security Requirements](#11-security-requirements)
12. [Performance & Metrics](#12-performance--metrics)
13. [Constraints & Assumptions](#13-constraints--assumptions)
14. [Architectural Decisions & Trade-offs](#14-architectural-decisions--trade-offs)
15. [Roadmap](#15-roadmap)
16. [Glossary](#16-glossary)

---

## 1. Executive Summary

Xmore is a production-running AI-powered stock signal platform purpose-built for the Egyptian Exchange (EGX). It aggregates output from five heterogeneous AI agents into a single daily consensus signal for approximately 190 EGX-listed stocks, then gates each signal through a friction-aware execution layer before publishing results to a bilingual web dashboard.

The platform targets three distinct user segments: retail traders seeking pre-market signals, professional investors requiring institutional-grade performance metrics, and prospective investors performing due diligence. All core functionality is available without registration; account creation unlocks personalised features (portfolio, alerts, forecast portfolios).

**Key architectural principle:** All Python computation runs exclusively in GitHub Actions on a scheduled basis. The Node.js API server on Render.com reads pre-computed values from PostgreSQL — it never invokes Python at request time. This is a hard platform constraint with deliberate design responses detailed in Section 14.

---

## 2. Business Context & Objectives

### 2.1 Problem Statement

The Egyptian retail investment market lacks accessible, transparent, and Arabic-native quantitative intelligence tools. Existing solutions suffer from one or more of the following deficiencies:

- **Signal opacity** — no explanation of methodology, no historical accountability
- **Friction blindness** — recommendations ignore EGX-specific transaction costs (stamp duty, FRA fees, Misr clearing), liquidity constraints, and daily ±10% price limits
- **Language exclusion** — all professional-grade tools are English-only
- **Benchmark misuse** — performance ratios calculated with US risk-free rates (5%) instead of Egypt CBE rate (27.25%), materially inflating reported Sharpe ratios

### 2.2 Business Objectives

| # | Objective | Measure |
|---|---|---|
| BO-1 | Provide daily pre-market AI consensus signals for all major EGX stocks | Coverage of ≥190 symbols, delivered by 09:00 Cairo daily |
| BO-2 | Filter signals through EGX-realistic friction to protect users from uneconomic trades | Edge ratio ≥ 3× round-trip cost required for approval |
| BO-3 | Publish a public, audited track record for investor transparency | Track record page accessible without login; updated daily |
| BO-4 | Serve Arabic-speaking users natively | Full RTL bilingual interface across all pages |
| BO-5 | Provide institutional-grade risk metrics calibrated for EGX | CBE rate (27.25%), 247 trading days used in all ratio calculations |
| BO-6 | Operate with zero manual daily intervention | Fully automated pipeline via GitHub Actions cron jobs |

---

## 3. Stakeholders

| Role | Description | Primary Touchpoint |
|---|---|---|
| **Retail trader** | EGX investor seeking daily buy/sell signals | Main dashboard (`/`) |
| **Active trader** | Intraday trader needing pivots, ATR, pattern recognition | Session Sheet (`/session`) |
| **Professional investor** | Portfolio manager requiring risk metrics and macro context | Xmore Pro (`/pro`), Track Record (`/track-record`) |
| **Prospective investor / LP** | Due diligence on Xmore's signal quality | Track Record (`/track-record`) |
| **System administrator** | Manages RAG documents, monitors pipeline health | Admin panel (`/admin`) |
| **Platform operator** | Maintains infrastructure, deploys updates | GitHub, Render.com |

---

## 4. Scope

### 4.1 In Scope

- AI signal generation for ~190 EGX-listed stocks (Sun–Thu trading calendar)
- Five-agent consensus engine with weighted voting
- Execution realism gate (costs, slippage, regime, trailing stops) — runs in CI pipeline
- Bilingual (EN/AR) web dashboard with dark/light theme
- Virtual portfolio tracking with EGP P&L accounting
- Price alerts (threshold-based, auto-triggered on page load)
- Forecast portfolio engine with 6 horizons (1m–2y)
- ETF data: 13 EGX-local funds (Mubasher), 4 global funds (yfinance)
- Live FX and gold prices with 90-day history
- Institutional performance metrics (EGX-correct Sharpe, Sortino, Calmar, IR, MDD)
- Universal investor scoring (6 output modes from a single composite score) — pre-computed in CI
- Public track record page with equity curve, walk-forward backtest, prediction log
- AI market assistant (Gemini RAG with full context injection)
- Macro brief (Gemini grounded web search)
- Session sheet (pivots, ATR, candlestick patterns, position simulator)
- Automated evaluation pipeline (D+1, D+5 signal outcome resolution)
- Walk-forward backtesting (weekly, per-symbol)
- Full bilingual documentation site (`/docs`)

### 4.2 Out of Scope

- Real-money brokerage integration (order placement)
- Real-time streaming prices (intraday signals use hourly snapshots)
- Coverage of non-EGX markets beyond ETF price display
- Mobile native application
- Options / derivatives trading signals (EGX derivatives not yet live)
- On-demand Python execution triggered by user API requests

---

## 5. Functional Requirements

### 5.1 Signal Generation (FR-SIG)

| ID | Requirement |
|---|---|
| FR-SIG-1 | System shall run 5 AI agents daily for each tracked EGX stock and record individual agent predictions |
| FR-SIG-2 | System shall compute a weighted consensus signal (BUY/HOLD/SELL) from agent votes |
| FR-SIG-3 | System shall compute the Xmore Score (0–100) as: `bull×0.30 + (100−bear)×0.25 + agreement_ratio×0.25 + avg_confidence×0.20` |
| FR-SIG-4 | System shall publish signals by 09:00 Cairo time on each EGX trading day |
| FR-SIG-5 | System shall ingest news headlines and compute sentiment (Positive/Neutral/Negative) via Gemini LLM |
| FR-SIG-6 | System shall evaluate signal outcomes at D+1 and D+5 by comparing predicted direction to actual close price |
| FR-SIG-7 | System shall record alpha (signal return minus EGX30 benchmark return) at D+1 and D+5 |

### 5.2 Execution Realism Gate (FR-EXEC)

All execution realism logic runs during the CI pipeline in `run_agents.py` via `apply_execution_realism()`. Results are persisted to the database before the Node.js API serves them. No execution calculations happen at request time.

| ID | Requirement |
|---|---|
| FR-EXEC-1 | Every BUY signal shall be evaluated against EGX full round-trip cost: brokerage (0.15%) + stamp duty (0.15%) + FRA fee (0.0125%) + EGX exchange fee (0.0125%) + Misr clearing (0.01%), × 2 legs |
| FR-EXEC-2 | Signals with edge ratio < 3× round-trip cost shall be blocked and logged to `blocked_signals` table |
| FR-EXEC-3 | System shall apply liquidity-tiered slippage: High ADV (>5M EGP/day) = 10 bps; Mid ADV (>1M EGP) = 25 bps; Low ADV = 60 bps |
| FR-EXEC-4 | System shall determine EGX30 market regime (BULL/NEUTRAL/BEAR) daily using MA20 distance; new long positions shall be blocked when regime = BEAR; regime state persisted to `regime_log` |
| FR-EXEC-5 | System shall model EGX daily ±10% price limits when computing realistic stop prices |
| FR-EXEC-6 | Open positions shall have a trailing stop activating on day 20 at 6% below peak, ratcheting up only, with hard exit on day 45 |
| FR-EXEC-7 | SELL and HOLD signals shall pass through execution gate unchanged |
| FR-EXEC-8 | All execution columns (`execution_approved`, `edge_ratio`, `realistic_fill_price`, `round_trip_cost_pct`, `regime_at_signal`) shall be pre-populated in `trade_recommendations` by the pipeline |

### 5.3 Dashboard (FR-DASH)

| ID | Requirement |
|---|---|
| FR-DASH-1 | Main dashboard shall display today's consensus signal, Xmore Score, confidence, agent agreement, and sentiment for each stock |
| FR-DASH-2 | Dashboard shall support stock screener filtering by signal, conviction, sector, and minimum confidence |
| FR-DASH-3 | Dashboard shall support full EN/AR language toggle with RTL layout |
| FR-DASH-4 | Dashboard shall support dark and light themes, persisted in localStorage |
| FR-DASH-5 | Dashboard shall display signal-level accuracy by agent and by horizon (D+5, D+10, D+20) |
| FR-DASH-6 | All pages shall be responsive (mobile, tablet, desktop) |

### 5.4 Session Sheet (FR-SESSION)

| ID | Requirement |
|---|---|
| FR-SESSION-1 | Session sheet shall display classic daily pivot levels (P, R1, R2, S1, S2) derived from prior session OHLC |
| FR-SESSION-2 | Session sheet shall display 14-day ATR (in EGP) and trend bias (bullish/neutral/bearish) |
| FR-SESSION-3 | System shall detect and display 8 candlestick patterns from the last 3 candles: Doji, Hammer, Shooting Star, Bullish Engulfing, Bearish Engulfing, Morning Star, Evening Star, Neutral |
| FR-SESSION-4 | Authenticated users shall be able to open and close virtual positions from today's BUY signals and track live P&L |

### 5.5 Portfolio & Alerts (FR-PORT)

| ID | Requirement |
|---|---|
| FR-PORT-1 | Users shall be able to create and track virtual stock positions with entry price, quantity, and entry date |
| FR-PORT-2 | System shall compute live cost vs market value and P&L in EGP for all open positions |
| FR-PORT-3 | Users shall be able to set price alerts (above/below threshold) for any EGX stock, up to 20 active alerts |
| FR-PORT-4 | Price alerts shall be evaluated automatically when the user opens the Portfolio tab; triggered alerts shall be marked as fired |

### 5.6 Forecast Portfolios (FR-FORE)

| ID | Requirement |
|---|---|
| FR-FORE-1 | Users shall be able to create named forecast portfolios with up to N stocks and a chosen horizon (1m, 2m, 3m, 6m, 1y, 2y) |
| FR-FORE-2 | System shall generate a per-stock expected return forecast using all active agents |
| FR-FORE-3 | System shall record daily actual closing prices and overlay them against forecasts on a chart |
| FR-FORE-4 | System shall generate a plain-language narrative describing portfolio phase, gap, and beat count |

### 5.7 Performance & Track Record (FR-PERF)

All performance metrics are pre-computed by the Python pipeline and stored in PostgreSQL. The Node.js API returns pre-computed rows; it performs no statistical calculations at request time.

| ID | Requirement |
|---|---|
| FR-PERF-1 | System shall compute EGX-correct Sharpe ratio using CBE rate (27.25% annual) and 247 trading days |
| FR-PERF-2 | System shall compute Sortino ratio (downside deviation only), Calmar ratio (return / max drawdown), and Information Ratio vs EGX30 |
| FR-PERF-3 | System shall compute max drawdown with peak date, trough date, and recovery status |
| FR-PERF-4 | System shall compute rolling 30-day Sharpe sparkline |
| FR-PERF-5 | Track record page shall be publicly accessible without authentication |
| FR-PERF-6 | Track record shall display equity curve (cumulative return vs EGX30), KPI strip with rolling windows (30/60/90 days), per-agent methodology cards, walk-forward backtest results, top stocks by alpha, and a paginated prediction log |
| FR-PERF-7 | Prediction log shall be exportable as CSV |
| FR-PERF-8 | Walk-forward backtest shall run weekly (every Sunday) for all tracked symbols and store results in `backtest_results` table |

### 5.8 Investor Scoring (FR-SCORE)

All scoring is computed during the daily pipeline and written to `scored_signals`. The API returns pre-stored rows.

| ID | Requirement |
|---|---|
| FR-SCORE-1 | System shall compute a composite investor score (0–1) for each signal: `consensus×0.40 + execution×0.25 + regime×0.20 + momentum×0.15` |
| FR-SCORE-2 | System shall translate the composite score into 6 output modes simultaneously: xmore_native (0–1), standard_100 (0–100 int), letter_grade (A+→F), stars (1–5, 0.5 resolution), signal_tier (S/A/B/C/D), conviction (HIGH/MEDIUM/LOW) |
| FR-SCORE-3 | All 6 format translations and a `meets_threshold` boolean shall be stored in `scored_signals.all_formats` (JSON column) at pipeline time |
| FR-SCORE-4 | Dashboard shall provide a mode selector UI allowing users to switch between all 6 formats without re-fetching |
| FR-SCORE-5 | API endpoints `GET /api/signals/scored`, `/scored/compare`, and `/morning-brief` shall be publicly available |

### 5.9 ETF & Rates (FR-ETF)

| ID | Requirement |
|---|---|
| FR-ETF-1 | System shall fetch and display data for ~13 EGX-listed ETFs from Mubasher (price, NAV, premium/discount, volume) |
| FR-ETF-2 | System shall fetch and display data for 4 global Egypt-focused ETFs (EGPT, EEMX, FM, FRDM) via yfinance |
| FR-ETF-3 | System shall display live FX rates: USD/EGP, USD/SAR, SAR/EGP |
| FR-ETF-4 | System shall display live gold prices: 24K, 21K, 18K per gram EGP and Gold Pound EGP |
| FR-ETF-5 | System shall store one FX/gold row per day in `fx_rates_history`, building a 90-day sparkline automatically |

### 5.10 AI Assistant & RAG (FR-RAG)

| ID | Requirement |
|---|---|
| FR-RAG-1 | Market assistant shall inject live market context (prices, signals, sentiment, ETF data, user portfolio) into every Gemini prompt |
| FR-RAG-2 | Uploaded PDF documents (ETF factsheets, market reports) shall be chunked and embedded via Gemini `text-embedding-004` |
| FR-RAG-3 | Market assistant shall perform semantic search over embedded documents when answering relevant questions |
| FR-RAG-4 | Macro brief shall use Gemini grounded web search to produce a structured real-time Egypt macro summary with web citations |

### 5.11 Authentication & Access Control (FR-AUTH)

| ID | Requirement |
|---|---|
| FR-AUTH-1 | Users shall be able to register and log in with email and password |
| FR-AUTH-2 | Session tokens shall be JWT stored in HTTP-only cookies |
| FR-AUTH-3 | Portfolio, alerts, and forecast portfolios shall be per-user, private, and inaccessible to other users |
| FR-AUTH-4 | Core signal data, performance metrics, and track record shall be accessible without authentication |
| FR-AUTH-5 | Admin panel shall require a separate admin credential (username + password checked against server-side env vars) |

---

## 6. Non-Functional Requirements

### 6.1 Availability
- Dashboard shall be available 24/7; planned downtime permitted only during EGX non-trading hours (Friday–Saturday)
- Signal pipeline shall complete by 09:00 Cairo time on each trading day

### 6.2 Performance
- API response time for standard signal endpoints: < 500 ms at p95 (all results are pre-computed; no Python at request time)
- Dashboard initial load: < 3 seconds on a 4G connection
- Database queries shall not perform full table scans on tables > 10,000 rows (indexes required)

### 6.3 Scalability
- System shall support concurrent access by up to 500 simultaneous users without degradation (Render.com PostgreSQL + connection pooling)
- ETF pipeline shall complete within 15 minutes for all 190+ symbols

### 6.4 Reliability
- GitHub Actions pipeline failures shall not corrupt existing data; each job is idempotent
- All database writes shall use upsert (INSERT OR REPLACE / ON CONFLICT DO UPDATE)
- PostgreSQL transaction errors shall be isolated per-row using SAVEPOINT/ROLLBACK TO SAVEPOINT
- If execution realism or scoring modules fail, the core pipeline continues without them (fail-open design)

### 6.5 Internationalisation
- All user-facing strings shall exist in both English and Arabic
- Arabic layout shall use RTL direction via `dir="rtl"` and appropriate CSS
- Date display shall account for EGX timezone (Africa/Cairo, UTC+2/+3 DST)

### 6.6 Maintainability
- No agent file shall be modified to add new pipeline functionality; new logic added as separate modules with hook integration
- New database tables shall be added to both `database.py` (`create_tables()`) and `web-ui/init-db.js`
- All constants (risk-free rate, trading days, slippage tiers) shall be centralised in `config/execution_config.py`

---

## 7. System Architecture

### 7.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│  (9 scheduled cron jobs — Sun–Thu + weekly)          │
│                                                      │
│  PYTHON EXECUTION BOUNDARY — all Python runs here   │
│  ─────────────────────────────────────────────────  │
│  run_agents.py                                       │
│    → 5 AI agents → consensus_engine.py              │
│    → apply_execution_realism() [friction gate]       │
│    → _populate_scored_signals() [6-mode scoring]     │
│    → evaluate_performance.py [D+1, D+5 outcomes]    │
│    → engines/backtest.py [weekly walk-forward]       │
│    → database.py writes to PostgreSQL               │
└──────────────────────┬──────────────────────────────┘
                       │ ALL results pre-computed and written
                       ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL (Render.com)                 │
│  36+ tables — signals, prices, news, performance,   │
│  ETF, portfolio, RAG, scoring, execution audit       │
│                                                      │
│  API boundary: Node.js reads; Python writes          │
└──────────────────────┬──────────────────────────────┘
                       │ SELECT only (no Python at request time)
                       ▼
┌─────────────────────────────────────────────────────┐
│          Node.js / Express API Server (Render)      │
│  web-ui/server.js — 11 route modules               │
│  SQLite wrapper (local) / pg Pool (production)      │
│  Returns pre-computed rows — zero Python calls      │
└──────────────────────┬──────────────────────────────┘
                       │ serves
                       ▼
┌─────────────────────────────────────────────────────┐
│            Vanilla JS Frontend                       │
│  Dashboard (app.js) · Pro (pro.js)                  │
│  Session (session.js) · Track Record (track-record.js)│
│  Time Machine (timemachine.js) · Docs (docs.html)   │
└─────────────────────────────────────────────────────┘
```

### 7.2 Deployment

| Component | Platform | Notes |
|---|---|---|
| Web server + API | Render.com (Node.js service) | Auto-deploys on push to `main` |
| PostgreSQL | Render.com managed PostgreSQL | Schema initialised by `init-db.js` on each deploy |
| Python pipeline | GitHub Actions (`ubuntu-latest`) | 9 cron jobs; connects to production PostgreSQL via `DATABASE_URL` |
| Static assets | Served by Express | `express.static()` from `web-ui/public/` |
| Domain | Render-provided | `xmore-project.onrender.com` |

### 7.3 Pre-computation Pattern (Critical)

Because Python cannot run on Render at request time, every calculated value that a user might want to see must be pre-computed during a pipeline run and written to the database. The API is a thin read layer.

**Pattern for each new metric:**

1. Python script computes metric during scheduled CI job
2. Metric is written to a named column or JSON field in PostgreSQL
3. Node.js route does a simple `SELECT` and returns the stored value
4. Frontend renders it directly — no in-browser calculation of statistical metrics

This pattern guarantees sub-500ms API responses and zero on-demand Python dependency.

---

## 8. Data Requirements

### 8.1 Core Tables (selected)

| Table | Purpose | Key columns |
|---|---|---|
| `prices` | Daily OHLCV per symbol | symbol, date, open, high, low, close, volume |
| `consensus_results` | Daily consensus signal per symbol | symbol, prediction_date, consensus_signal, xmore_score, bull, bear, is_live, is_simulated |
| `trade_recommendations` | Enriched signals with execution data | symbol, recommendation_date, action, confidence, edge_ratio, execution_approved, alpha_1d, alpha_5d, patterns, regime_at_signal |
| `scored_signals` | 6-mode composite scores (pre-computed) | symbol, signal_date, composite_score, all_formats (JSON), meets_threshold |
| `blocked_signals` | Audit log of rejected BUY signals | ticker, signal_date, block_reason, regime_at_block |
| `regime_log` | Daily market regime history | date, regime, egx30_price, ma20, distance_pct |
| `user_positions` | Virtual portfolio positions | user_id, symbol, entry_price, quantity, exit_price, return_pct |
| `backtest_results` | Weekly walk-forward results | symbol, run_date, accuracy, directional_accuracy, signal_pnl_pct |
| `fx_rates_history` | Daily FX and gold rates | date, USD_EGP, XAU_USD, GOLD_24K_EGP_G |
| `instrument` | ETF master data | symbol, name, type, issuer, currency |
| `rag_chunks` | Embedded document chunks | doc_id, chunk_text, embedding (JSON) |

### 8.2 Data Retention

- Price history: indefinite (append-only)
- News: indefinite (headline + sentiment)
- Signal evaluations: indefinite (audit trail)
- Blocked signals: indefinite (never delete — compliance)
- RAG embeddings: retained until document is deleted by admin

### 8.3 Data Sources

| Source | Data | Frequency |
|---|---|---|
| yfinance | EGX stock OHLCV, ETF prices, EGX30 index | Daily + intraday |
| Mubasher (scraper) | EGX-listed ETF prices, NAV, volume | Daily |
| NewsAPI / Finnhub | Market headlines for sentiment | Intraday (3×/day) |
| open.er-api.com | FX rates + gold | On-demand (page load via Node.js) |
| Google Gemini 2.5 Flash | Sentiment, briefs, macro, RAG, chat | On-demand (Gemini API called from Node.js for chat/macro; from Python for signal sentiment) |

---

## 9. Integrations & External Dependencies

| Service | Purpose | Credential | Caller |
|---|---|---|---|
| **Google Gemini API** | LLM agent, sentiment (Python), RAG embeddings, macro brief, market assistant (Node.js) | `GOOGLE_API_KEY` | Both |
| **NewsAPI** | Market news headlines | `NEWS_API_KEY` | Python (CI) |
| **Finnhub** | Supplementary financial data | `FINNHUB_API_KEY` | Python (CI) |
| **yfinance** | EGX stock prices, ETF prices, EGX30 index | — | Python (CI) |
| **Mubasher** | EGX ETF NAV and prices (web scraper) | — | Python (CI) |
| **open.er-api.com** | FX rates (no key required) | — | Node.js (request-time) |
| **Render.com** | Hosting, PostgreSQL, managed TLS | Render account | — |
| **GitHub Actions** | Scheduled pipeline CI/CD | `DATABASE_URL`, secrets | — |

---

## 10. Automated Pipeline

### 10.1 Scheduled Jobs

| Job | Cron (UTC) | Cairo Time | Days | Purpose |
|---|---|---|---|---|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | 09:00–14:00 | Sun–Thu | Live price snapshots during trading session |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | 09:00, 11:00, 13:00 | Sun–Thu | Refresh news + sentiment 3× during session |
| `post-market-pipeline` | `30 12 * * 0-4` | 14:30 | Sun–Thu | Store closing prices, trigger evaluation |
| `egx-daily-snapshot` | `0 14 * * 0-4` | 16:00 | Sun–Thu | Final daily data snapshot |
| `daily-pipeline` | `0 22 * * 0-5` | 00:00+1 | Sun–Fri | Run all 5 agents → consensus → execution gate → scoring |
| `catchup-evaluation` | `0 * * * *` | Hourly | Daily | Resolve any pending D+1/D+5 outcomes |
| `etf-egx-all` | `30 13 * * 0-4` | 15:30 | Sun–Thu | Fetch EGX ETF prices, NAV, volumes |
| `etf-global-prices` | `30 21 * * 1-5` | 23:30 | Mon–Fri | Fetch global ETF prices from yfinance |
| `weekly-backtest` | `0 7 * * 0` | 09:00 | Sunday | Walk-forward backtest all symbols |

### 10.2 Pipeline Design Principles

- **Idempotent** — all inserts use upsert; re-running a job produces identical state
- **Fail-safe** — individual row errors do not abort the batch (SAVEPOINT isolation per row)
- **Fail-open** — if execution realism or scoring modules are unavailable, the pipeline continues without them; partial results are better than zero results
- **Audit-logged** — blocked signals, regime state, and evaluation outcomes are all persisted
- **No manual steps** — zero human intervention required for normal operation
- **Pre-computation first** — every value the API needs must be written to the database during the pipeline run, not calculated on demand

---

## 11. Security Requirements

| Requirement | Implementation |
|---|---|
| Authentication | JWT in HTTP-only cookie (prevents XSS token theft) |
| Password storage | Bcrypt hashing (never stored in plain text) |
| API secrets | Environment variables only; never in source code or logs |
| SQL injection prevention | Parameterised queries throughout (no string interpolation in SQL) |
| Admin access | Separate credential checked against `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars; not the user auth system |
| CORS | Configured to restrict cross-origin requests in production |
| Input validation | All user-supplied parameters parsed and bounded before use (e.g., `days` clamped to max 365) |

---

## 12. Performance & Metrics

### 12.1 Signal Quality KPIs

| Metric | Definition | Calibration |
|---|---|---|
| Directional accuracy | % of signals where predicted direction = actual direction at D+1 | Evaluated daily by `evaluate_performance.py` |
| Alpha (D+1) | Signal return − EGX30 return at D+1 | Stored in `alpha_1d` column |
| Alpha (D+5) | Signal return − EGX30 return at D+5 | Stored in `alpha_5d` column |
| Sharpe ratio | `(mean_excess_return / std_return) × sqrt(247)` | Risk-free rate: CBE 27.25% annual; 247 EGX days |
| Sortino ratio | `(mean_excess_return / downside_std) × sqrt(247)` | Downside-only deviation |
| Calmar ratio | `annualised_return / abs(max_drawdown)` | Minimum 20 data points required |
| Information ratio | `mean_alpha / std_alpha` | vs EGX30 benchmark |
| Max drawdown | Peak-to-trough equity curve decline | With recovery date and duration |

### 12.2 Execution Gate KPIs

| Metric | Definition |
|---|---|
| Approval rate | % of BUY signals that pass the edge filter and regime check |
| Block reason distribution | Breakdown of blocked signals by reason (edge, regime, data) |
| Average edge ratio | Mean signal expected return ÷ round-trip cost for approved signals |

### 12.3 Investor Scoring Thresholds

| Mode | Example | Actionable threshold |
|---|---|---|
| xmore_native | 0.84 | ≥ 0.62 |
| standard_100 | 84 | ≥ 62 |
| letter_grade | A | ≥ B |
| stars | ★★★★☆ | ≥ 3.5 |
| signal_tier | A | ≥ B |
| conviction | HIGH | ≥ MEDIUM |

---

## 13. Constraints & Assumptions

### 13.1 Python on Render — Architectural Constraint

**Constraint:** Render.com hosts Xmore as a Node.js (`env: node`) service. Python cannot be installed or executed on the Render web dyno. There is no worker dyno in the current tier.

**Implication:** Every value that the Node.js API needs to return must already exist in the PostgreSQL database before the API request arrives. This means:

- The execution realism layer (`execution_agent.py`, `regime_filter.py`, `holding_manager.py`) runs during the GitHub Actions `daily-pipeline` job — not when a user clicks a button
- The investor scoring system (`scoring_formatter.py`) runs during `daily-pipeline` and writes to `scored_signals` — the API reads the row, it never calls Python
- Performance metrics (`performance_metrics.py`) are computed during `catchup-evaluation` — the `/api/performance-v2/summary` endpoint returns pre-computed figures
- Regime state is determined once per day in CI and stored in `regime_log` — the API returns the most recent stored regime

**What this is NOT a limitation for:**

| Feature | Works fine because… |
|---|---|
| Gemini market assistant / macro brief | Gemini API is called directly from Node.js at request time |
| FX & gold rates | open.er-api.com is called from Node.js at request time |
| Virtual P&L simulator | Pure arithmetic in Node.js, no Python needed |
| Signal display | Reads pre-computed rows |
| Track record equity curve | Reads pre-computed rows; chart drawn client-side |

**Improvement path (Section 14.1):**

The pre-computation pattern is intentional and performant — it means the API always returns instantly. Future improvements include adding a Render Background Worker (paid tier) for on-demand Python if real-time regime checks on user-requested symbols become a product requirement.

### 13.2 Other Constraints

- **EGX trading calendar**: Sunday–Thursday; Friday and Saturday are non-trading days. All pipeline jobs and holding-day calculations use this calendar.
- **EGX daily price limit**: ±10% maximum move per session. Stop-loss orders can gap through this limit; the execution layer accounts for this.
- **Render.com free tier**: Auto-spins down after inactivity; first request after spin-down may have cold-start latency of 30–60 seconds.
- **yfinance dependency**: EGX data quality from Yahoo Finance is occasionally stale or missing; the pipeline handles this gracefully (fail-open, `NaN` checks before calculations).
- **Gemini API quotas**: Gemini 2.5 Flash has rate limits; sentiment generation includes retry logic.

### 13.3 Assumptions

- The Egypt CBE overnight deposit rate (currently 27.25%) will be reviewed quarterly and updated in `config/execution_config.py`.
- EGX trading days per year (currently 247) will be reviewed annually for holiday adjustments.
- The EGX30 index (`^CASE30` on Yahoo Finance) is used as the performance benchmark throughout.
- Historical simulation data (60 days via `backfill_predictions.py`) is treated as transparent supplementary data — not presented as live performance. Simulated signals are tagged `SIM` in the prediction log.

---

## 14. Architectural Decisions & Trade-offs

### 14.1 Pre-computation vs On-demand Python

**Decision:** All Python calculations are batch/scheduled, never request-time.

**Rationale:**
- Render.com `env: node` does not support Python — this is a hard platform constraint
- Pre-computing during CI means the API response time is independent of calculation complexity
- A signal for 190 stocks with execution scoring would take 10–30 seconds to compute on demand; from the database it takes < 50 ms
- The pipeline already runs before market open — results are ready when users need them

**Trade-off:** Regime state and scoring are 12–24 hours old by the time a user views them in the evening. For an end-of-day pre-market signal product this is acceptable — the signal itself is also a point-in-time calculation.

**Future upgrade path:** A Render Background Worker (paid tier) or a dedicated Python microservice could enable on-demand re-scoring when a user requests it for a specific symbol. This would require duplicating the scoring logic in a stateless API-friendly form.

### 14.2 SQLite Local / PostgreSQL Production Dual-mode

**Decision:** `database.py` and `server.js` detect `DATABASE_URL` env var to switch between SQLite and PostgreSQL automatically.

**Rationale:** Enables offline development without a database server. All queries use a `.all()/.get()/.run()` wrapper that maps between the two APIs.

**Constraint:** Never use `.query()` on the wrapper — it maps to `pg.Pool.query()` only and breaks SQLite mode.

### 14.3 No Agent Modification Policy

**Decision:** New pipeline features (execution realism, scoring, metrics) are added as separate Python modules, never by modifying the 5 agent files.

**Rationale:** Agents are independently testable black boxes. Mixing cross-cutting concerns (cost models, regime state) into agent logic would make each agent harder to unit-test and introduce subtle bugs where agent output changes based on market state that should be downstream.

### 14.4 JavaScript-only Frontend

**Decision:** No framework (React/Vue/Svelte); vanilla JS with ES6 modules.

**Rationale:** Reduces build complexity, eliminates hydration overhead, and is directly servable by Express static middleware. Given the scope of the project (pre-market signals, one primary user interaction: viewing a table), the framework overhead is not justified.

---

## 15. Roadmap

### 15.1 Near-term
- [ ] Real-time intraday signal updates (websocket or SSE feed from Node.js)
- [ ] Push notifications (email / Telegram) when a signal changes from HOLD to BUY
- [ ] Options on EGX derivatives when the exchange enables them
- [ ] Brokerage API integration (direct order placement)
- [ ] Render Background Worker for on-demand scoring (Python) — removes the batch-only constraint

### 15.2 Medium-term
- [ ] Paid Pro tier with advanced screener and direct API access key
- [ ] Portfolio optimiser (mean-variance, EGX constraints)
- [ ] Mobile app (React Native, sharing the same API)
- [ ] Expansion to ADX (Abu Dhabi) and Tadawul (Saudi)

### 15.3 Architectural Improvements
- [ ] On-demand regime re-check via a stateless Python microservice (FastAPI on a worker dyno) — eliminates the 24h staleness for regime state
- [ ] Pre-compute performance metrics during `daily-pipeline` rather than `catchup-evaluation` to have them ready for overnight users
- [ ] Streaming evaluation: compute D+1 outcomes at 14:30 Cairo (post-market) rather than waiting for the catchup cron

---

## 16. Glossary

| Term | Definition |
|---|---|
| **ADV** | Average Daily Volume — average shares traded per day, used for liquidity tiering |
| **Alpha** | Excess return above the EGX30 benchmark at a given horizon |
| **ATR** | Average True Range — measure of daily price volatility in EGP |
| **BPS** | Basis points — 1 bps = 0.01% |
| **Calmar Ratio** | Annualised return divided by maximum drawdown |
| **CBE** | Central Bank of Egypt — sets the overnight deposit rate used as risk-free rate |
| **Composite Score** | Weighted combination of consensus (40%), execution (25%), regime (20%), and momentum (15%) sub-scores |
| **Consensus Signal** | BUY / HOLD / SELL derived from majority-weighted agent vote |
| **D+1 / D+5** | Evaluation horizons — 1 trading day or 5 trading days after signal date |
| **EGX** | Egyptian Exchange — the primary stock exchange of Egypt |
| **EGX30** | The EGX blue-chip index of the 30 most liquid Egyptian stocks |
| **Edge Ratio** | Signal expected return ÷ round-trip transaction cost |
| **IR** | Information Ratio — consistency of alpha generation relative to its volatility |
| **MDD** | Maximum Drawdown — largest peak-to-trough decline in the equity curve |
| **NAV** | Net Asset Value — per-unit fair value of an ETF |
| **Pivot Levels** | Support/resistance levels calculated from prior session's High, Low, and Close |
| **Pre-computation Pattern** | All Python metrics computed during CI pipeline jobs and stored in PostgreSQL; Node.js API reads stored values only |
| **RAG** | Retrieval-Augmented Generation — using embedded document chunks to ground AI answers |
| **Regime** | Market state (BULL / NEUTRAL / BEAR) based on EGX30 vs its 20-day moving average; determined once daily in CI |
| **Round-trip cost** | Total transaction cost for entering and exiting a position (both legs) |
| **Sharpe Ratio** | Risk-adjusted excess return: `(mean_return − RF) / std_return × sqrt(trading_days)` |
| **SIM** | Simulated — tag applied to historical backfill predictions, distinct from live signals |
| **Sortino Ratio** | Like Sharpe but only penalises downside volatility |
| **Trailing Stop** | A stop-loss that only moves in the direction of profit, never against it |
| **Xmore Score** | Proprietary 0–100 bullishness composite across all agent votes |

---

*Xmore — AI Stock Intelligence for the Egyptian Exchange*
*Version 1.2 · March 2026*
