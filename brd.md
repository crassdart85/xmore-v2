# Business Requirements Document (BRD)
## Xmore — AI Stock Intelligence Platform for the Egyptian Exchange

| Field | Detail |
|---|---|
| **Document version** | 1.0 |
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
14. [Glossary](#14-glossary)

---

## 1. Executive Summary

Xmore is a production-running AI-powered stock signal platform purpose-built for the Egyptian Exchange (EGX). It aggregates output from five heterogeneous AI agents into a single daily consensus signal for approximately 190 EGX-listed stocks, then gates each signal through a friction-aware execution layer before publishing results to a bilingual web dashboard.

The platform targets three distinct user segments: retail traders seeking pre-market signals, professional investors requiring institutional-grade performance metrics, and prospective investors performing due diligence. All core functionality is available without registration; account creation unlocks personalised features (portfolio, alerts, forecast portfolios).

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
- Execution realism gate (costs, slippage, regime, trailing stops)
- Bilingual (EN/AR) web dashboard with dark/light theme
- Virtual portfolio tracking with EGP P&L accounting
- Price alerts (threshold-based, auto-triggered on page load)
- Forecast portfolio engine with 6 horizons (1m–2y)
- ETF data: 13 EGX-local funds (Mubasher), 4 global funds (yfinance)
- Live FX and gold prices with 90-day history
- Institutional performance metrics (EGX-correct Sharpe, Sortino, Calmar, IR, MDD)
- Universal investor scoring (6 output modes from a single composite score)
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

| ID | Requirement |
|---|---|
| FR-EXEC-1 | Every BUY signal shall be evaluated against EGX full round-trip cost: brokerage (0.15%) + stamp duty (0.15%) + FRA fee (0.0125%) + EGX exchange fee (0.0125%) + Misr clearing (0.01%), × 2 legs |
| FR-EXEC-2 | Signals with edge ratio < 3× round-trip cost shall be blocked and logged to `blocked_signals` table |
| FR-EXEC-3 | System shall apply liquidity-tiered slippage: High ADV (>5M EGP/day) = 10 bps; Mid ADV (>1M EGP) = 25 bps; Low ADV = 60 bps |
| FR-EXEC-4 | System shall determine EGX30 market regime (BULL/NEUTRAL/BEAR) daily using MA20 distance; new long positions shall be blocked when regime = BEAR |
| FR-EXEC-5 | System shall model EGX daily ±10% price limits when computing realistic stop prices |
| FR-EXEC-6 | Open positions shall have a trailing stop activating on day 20 at 6% below peak, ratcheting up only, with hard exit on day 45 |
| FR-EXEC-7 | SELL and HOLD signals shall pass through execution gate unchanged |

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

| ID | Requirement |
|---|---|
| FR-SCORE-1 | System shall compute a composite investor score (0–1) for each signal: `consensus×0.40 + execution×0.25 + regime×0.20 + momentum×0.15` |
| FR-SCORE-2 | System shall translate the composite score into 6 output modes simultaneously: xmore_native (0–1), standard_100 (0–100 int), letter_grade (A+→F), stars (1–5, 0.5 resolution), signal_tier (S/A/B/C/D), conviction (HIGH/MEDIUM/LOW) |
| FR-SCORE-3 | Dashboard shall provide a mode selector UI allowing users to switch between all 6 formats without re-fetching |
| FR-SCORE-4 | API endpoints `GET /api/signals/scored`, `/scored/compare`, and `/morning-brief` shall be publicly available |

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
- API response time for standard signal endpoints: < 500 ms at p95
- Dashboard initial load: < 3 seconds on a 4G connection
- Database queries shall not perform full table scans on tables > 10,000 rows (indexes required)

### 6.3 Scalability
- System shall support concurrent access by up to 500 simultaneous users without degradation (Render.com PostgreSQL + connection pooling)
- ETF pipeline shall complete within 15 minutes for all 190+ symbols

### 6.4 Reliability
- GitHub Actions pipeline failures shall not corrupt existing data; each job is idempotent
- All database writes shall use upsert (INSERT OR REPLACE / ON CONFLICT DO UPDATE)
- PostgreSQL transaction errors shall be isolated per-row using SAVEPOINT/ROLLBACK TO SAVEPOINT

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
└──────────────┬──────────────────────────────────────┘
               │ runs Python scripts
               ▼
┌─────────────────────────────────────────────────────┐
│              Python Agent Engine                     │
│  run_agents.py → 5 agents → consensus_engine.py     │
│       → execution_agent.py (friction gate)          │
│       → scoring_formatter.py (6-mode score)         │
│       → database.py (PostgreSQL / SQLite)           │
└──────────────┬──────────────────────────────────────┘
               │ writes to
               ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL (Render.com)                 │
│  36 tables — signals, prices, news, performance,    │
│  ETF, portfolio, RAG, scoring, execution audit       │
└──────────────┬──────────────────────────────────────┘
               │ queried by
               ▼
┌─────────────────────────────────────────────────────┐
│          Node.js / Express API Server               │
│  web-ui/server.js — 10 route modules               │
│  SQLite wrapper (local) / pg Pool (production)      │
└──────────────┬──────────────────────────────────────┘
               │ serves
               ▼
┌─────────────────────────────────────────────────────┐
│            Vanilla JS Frontend                       │
│  Dashboard (app.js) · Pro (pro.js)                  │
│  Session (session.js) · Track Record (track-record.js)│
│  Time Machine (timemachine.js)                       │
└─────────────────────────────────────────────────────┘
```

### 7.2 Deployment

| Component | Platform | Notes |
|---|---|---|
| Web server + API | Render.com (Node.js service) | Auto-deploys on push to `main` |
| PostgreSQL | Render.com managed PostgreSQL | Schema initialised by `init-db.js` on each deploy |
| Python pipeline | GitHub Actions | Runs on `ubuntu-latest` runners; SQLite not used in CI |
| Static assets | Served by Express | `express.static()` from `web-ui/public/` |
| Domain | Render-provided | `xmore-project.onrender.com` |

---

## 8. Data Requirements

### 8.1 Core Tables (selected)

| Table | Purpose | Key columns |
|---|---|---|
| `prices` | Daily OHLCV per symbol | symbol, date, open, high, low, close, volume |
| `consensus_results` | Daily consensus signal per symbol | symbol, prediction_date, consensus_signal, xmore_score, bull, bear, is_live, is_simulated |
| `trade_recommendations` | Enriched signals with execution data | symbol, recommendation_date, action, confidence, edge_ratio, execution_approved, alpha_1d, alpha_5d, patterns |
| `scored_signals` | 6-mode composite scores | symbol, signal_date, composite_score, all_formats (JSON), meets_threshold |
| `blocked_signals` | Audit log of rejected BUY signals | ticker, signal_date, block_reason, regime_at_block |
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
| open.er-api.com | FX rates + gold | On-demand (page load) |
| Google Gemini 2.5 Flash | Sentiment, briefs, macro, RAG, chat | On-demand |

---

## 9. Integrations & External Dependencies

| Service | Purpose | Credential |
|---|---|---|
| **Google Gemini API** | LLM agent, sentiment, RAG embeddings, macro brief, market assistant | `GOOGLE_API_KEY` |
| **NewsAPI** | Market news headlines | `NEWS_API_KEY` |
| **Finnhub** | Supplementary financial data | `FINNHUB_API_KEY` |
| **yfinance** | EGX stock prices, ETF prices, EGX30 index (no key required) | — |
| **Mubasher** | EGX ETF NAV and prices (web scraper) | — |
| **open.er-api.com** | FX rates (no key required) | — |
| **Render.com** | Hosting, PostgreSQL, managed TLS | Render account |
| **GitHub Actions** | Scheduled pipeline CI/CD | `DATABASE_URL`, secrets |

---

## 10. Automated Pipeline

### 10.1 Scheduled Jobs

| Job | Cron (UTC) | Cairo Time | Purpose |
|---|---|---|---|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | 09:00–14:00 | Live price snapshots during trading session |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | 09:00, 11:00, 13:00 | Refresh news + sentiment 3× during session |
| `post-market-pipeline` | `30 12 * * 0-4` | 14:30 | Store closing prices, trigger evaluation |
| `egx-daily-snapshot` | `0 14 * * 0-4` | 16:00 | Final daily data snapshot |
| `daily-pipeline` | `0 22 * * 0-5` | 00:00+1 | Run all 5 agents, produce next-day signals |
| `catchup-evaluation` | `0 * * * *` | Hourly | Resolve any pending D+1/D+5 outcomes |
| `etf-egx-all` | `30 13 * * 0-4` | 15:30 | Fetch EGX ETF prices, NAV, volumes |
| `etf-global-prices` | `30 21 * * 1-5` | 23:30 | Fetch global ETF prices from yfinance |
| `weekly-backtest` | `0 7 * * 0` | 09:00 Sunday | Walk-forward backtest all symbols |

### 10.2 Pipeline Design Principles

- **Idempotent** — all inserts use upsert; re-running a job produces identical state
- **Fail-safe** — individual row errors do not abort the batch (SAVEPOINT isolation)
- **Fail-open** — if execution realism or scoring modules are unavailable, the pipeline continues without them
- **Audit-logged** — blocked signals, regime state, and evaluation outcomes are all persisted
- **No manual steps** — zero human intervention required for normal operation

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
| Directional accuracy | % of signals where predicted direction = actual direction at D+1 | Evaluated daily |
| Alpha (D+1) | Signal return − EGX30 return at D+1 | Stored in `alpha_1d` |
| Alpha (D+5) | Signal return − EGX30 return at D+5 | Stored in `alpha_5d` |
| Sharpe ratio | `(mean_excess_return / std_return) × sqrt(247)` | Risk-free rate: CBE 27.25% annual |
| Sortino ratio | `(mean_excess_return / downside_std) × sqrt(247)` | Downside-only deviation |
| Calmar ratio | `annualised_return / abs(max_drawdown)` | Minimum 20 data points |
| Information ratio | `mean_alpha / std_alpha` | vs EGX30 benchmark |
| Max drawdown | Peak-to-trough equity curve decline | With recovery date and duration |

### 12.2 Execution Gate KPIs

| Metric | Definition |
|---|---|
| Approval rate | % of BUY signals that pass the edge filter and regime check |
| Block reason distribution | Breakdown of blocked signals by reason (edge, regime, data) |
| Average edge ratio | Mean signal expected return ÷ round-trip cost for approved signals |

### 12.3 Investor Scoring Thresholds

| Mode | Actionable threshold |
|---|---|
| xmore_native | ≥ 0.62 |
| standard_100 | ≥ 62 |
| letter_grade | ≥ B |
| stars | ≥ 3.5 |
| signal_tier | ≥ B |
| conviction | ≥ MEDIUM |

---

## 13. Constraints & Assumptions

### 13.1 Constraints

- **EGX trading calendar**: Sunday–Thursday; Friday and Saturday are non-trading days. All pipeline jobs and holding-day calculations use this calendar.
- **EGX daily price limit**: ±10% maximum move per session. Stop-loss orders can gap through this limit; the execution layer accounts for this.
- **Render.com free tier**: Auto-spins down after inactivity; first request after spin-down may have cold-start latency of 30–60 seconds.
- **yfinance dependency**: EGX data quality from Yahoo Finance is occasionally stale or missing; the pipeline handles this gracefully (fail-open).
- **Gemini API quotas**: Gemini 2.5 Flash has rate limits; sentiment and brief generation includes retry logic and result caching.
- **Python on Render**: Render `env: node` does not execute Python. All Python logic runs exclusively via GitHub Actions.

### 13.2 Assumptions

- The Egypt CBE overnight deposit rate (currently 27.25%) will be reviewed quarterly and updated in `config/execution_config.py`.
- EGX trading days per year (currently 247) will be reviewed annually for holiday adjustments.
- The EGX30 index (`^CASE30` on Yahoo Finance) is used as the performance benchmark throughout.
- Historical simulation data (60 days via `backfill_predictions.py`) is treated as transparent supplementary data — not presented as live performance.

---

## 14. Glossary

| Term | Definition |
|---|---|
| **ADV** | Average Daily Volume — average shares traded per day, used for liquidity tiering |
| **Alpha** | Excess return above the EGX30 benchmark at a given horizon |
| **ATR** | Average True Range — measure of daily price volatility in EGP |
| **BPS** | Basis points — 1 bps = 0.01% |
| **Calmar Ratio** | Annualised return divided by maximum drawdown |
| **CBE** | Central Bank of Egypt — sets the overnight deposit rate used as risk-free rate |
| **Composite Score** | Weighted combination of consensus, execution, regime, and momentum sub-scores |
| **Consensus Signal** | BUY / HOLD / SELL derived from majority-weighted agent vote |
| **D+1 / D+5** | Evaluation horizons — 1 trading day or 5 trading days after signal date |
| **EGX** | Egyptian Exchange — the primary stock exchange of Egypt |
| **EGX30** | The EGX blue-chip index of the 30 most liquid Egyptian stocks |
| **Edge Ratio** | Signal expected return ÷ round-trip transaction cost |
| **IR** | Information Ratio — consistency of alpha generation relative to its volatility |
| **MDD** | Maximum Drawdown — largest peak-to-trough decline in the equity curve |
| **NAV** | Net Asset Value — per-unit fair value of an ETF |
| **Pivot Levels** | Support/resistance levels calculated from prior session's High, Low, and Close |
| **RAG** | Retrieval-Augmented Generation — using embedded document chunks to ground AI answers |
| **Regime** | Market state (BULL / NEUTRAL / BEAR) based on EGX30 vs its 20-day moving average |
| **Round-trip cost** | Total transaction cost for entering and exiting a position (both legs) |
| **Sharpe Ratio** | Risk-adjusted excess return: `(mean_return − RF) / std_return × sqrt(trading_days)` |
| **SIM** | Simulated — tag applied to historical backfill predictions, distinct from live signals |
| **Sortino Ratio** | Like Sharpe but only penalises downside volatility |
| **Trailing Stop** | A stop-loss that only moves in the direction of profit, never against it |
| **Xmore Score** | Proprietary 0–100 bullishness composite across all agent votes |

---

*Xmore — AI Stock Intelligence for the Egyptian Exchange*
*Version 1.0 · March 2026*
