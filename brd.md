# Business Requirements Document (BRD)
## Xmore — AI Stock & Fund Intelligence Platform for the Egyptian Exchange

| Field | Detail |
|---|---|
| **Document version** | 1.4 |
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

Xmore is a production-running AI-powered market intelligence platform purpose-built for the Egyptian Exchange (EGX). It aggregates output from six heterogeneous AI agents into a daily consensus signal for approximately 190 EGX-listed stocks, then applies a four-layer pipeline — weighted vote, friction-aware execution gate, risk filter, and regime gate — before publishing results to a bilingual web dashboard.

Signals are independently validated each week using walk-forward backtesting (90-day train / 20-day test / 10-day step rolling windows), providing institutional-grade out-of-sample proof of edge.

The platform extends signal generation to EGX-listed ETFs and ETPs using a dedicated technical signal engine (MA crossover, RSI, NAV premium/discount, momentum). The AI research assistant has full awareness of live market data, regime state, backtest results, signal distribution, ETF NAV/AUM, and agent performance — making it one of the most contextually rich EGX-native market assistants available.

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
- **No regime awareness** — signals ignore macro market state, generating buy signals during crisis periods
- **ETF blindspot** — no quantitative signal engine exists for EGX-listed funds and ETPs

### 2.2 Business Objectives

| # | Objective | Measure |
|---|---|---|
| BO-1 | Provide daily pre-market AI consensus signals for all major EGX stocks | Coverage of ≥190 symbols, delivered by 09:00 Cairo daily |
| BO-2 | Filter signals through EGX-realistic friction to protect users from uneconomic trades | Edge ratio ≥ 3× round-trip cost required for approval |
| BO-3 | Publish a public, audited track record with walk-forward validation | Track record page with 10+ metrics, accessible without login; updated daily |
| BO-4 | Serve Arabic-speaking users natively | Full RTL bilingual interface across all pages |
| BO-5 | Provide institutional-grade risk metrics calibrated for EGX | CBE rate (27.25%), 247 trading days used in all ratio calculations |
| BO-6 | Operate with zero manual daily intervention | Fully automated pipeline via GitHub Actions cron jobs |
| BO-7 | Extend signals to ETF and ETP instruments | Daily signals for all active LOCAL_EGX instruments (MA, RSI, NAV premium) |
| BO-8 | Provide regime-aware signal gating | Crisis regime blocks UP signals; Turbulent downgrades conviction |

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
- Six-agent consensus engine with weighted voting and four-layer pipeline
- Confidence gating: signals with max(probability) < 60% converted to HOLD
- Per-symbol LightGBM models (Optuna-tuned HPO, 25 trials, cached)
- Walk-forward validation harness (weekly, per-symbol, 6 agents)
- Regime-aware signal gating (Layer 4): HMM-based Calm / Turbulent / Crisis detection
- ETF/ETP signal engine: MA crossover, RSI, NAV premium/discount, momentum for all active instruments
- Execution realism gate (costs, slippage, regime, trailing stops) — runs in CI pipeline
- Bilingual (EN/AR) web dashboard with dark/light theme
- Market regime banner on main dashboard (live Calm/Turbulent/Crisis indicator)
- Virtual portfolio tracking with EGP P&L accounting
- Price alerts (threshold-based, auto-triggered on page load)
- Forecast portfolio engine with 6 horizons (1m–2y)
- ETF data: 13 EGX-local funds, 4 global Egypt-focused funds; plus daily technical signals
- Live FX and gold prices with 90-day history
- Institutional performance metrics (EGX-correct Sharpe, Sortino, Calmar, IR, MDD)
- Universal investor scoring (6 output modes from a single composite score) — pre-computed in CI
- Public track record page: equity curve, walk-forward backtest, signal distribution, sector accuracy, regime-aware stats, methodology comparison, agent accountability, rolling windows, ETF signals, prediction log
- AI market assistant (Gemini RAG): injected with regime state, backtest results, signal distribution, ETF NAV/AUM/signals, agent performance, news, portfolio context
- Macro brief (Gemini grounded web search)
- Session sheet (pivots, ATR, candlestick patterns, position simulator)
- Custom news source ingestion (URL/RSS/manual feeds via admin panel)
- Automated evaluation pipeline (D+1, D+5 signal outcome resolution)
- Walk-forward backtesting (weekly, per-symbol)
- Full bilingual documentation site (`/docs`)
- Landing page (`/landing`) for pitch and investor overview

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
| FR-SIG-1 | System shall run 6 AI agents daily for each tracked EGX stock: ML (LightGBM per-symbol), MA (adaptive periods), RSI (adaptive periods), Gemini Sentiment, Volume, and Risk |
| FR-SIG-2 | System shall compute a weighted consensus signal (BUY/HOLD/SELL) using a four-layer pipeline: agent vote → weighted average → risk filter → regime gate |
| FR-SIG-3 | System shall compute the Xmore Score (0–100): `bull×0.30 + (100−bear)×0.25 + agreement_ratio×0.25 + avg_confidence×0.20` |
| FR-SIG-4 | System shall publish signals by 09:00 Cairo time on each EGX trading day |
| FR-SIG-5 | System shall ingest news headlines and compute sentiment (Positive/Neutral/Negative) via Gemini with recency decay (half-life 1.5 days) |
| FR-SIG-6 | System shall evaluate signal outcomes at D+1 and D+5 by comparing predicted direction to actual close price |
| FR-SIG-7 | System shall record alpha (signal return minus EGX30 benchmark return) at D+1 and D+5 |
| FR-SIG-8 | Signals with max(agent probability) < 60% shall be gated to HOLD before consensus (confidence gating) |
| FR-SIG-9 | Layer 4 regime gate shall block UP signals during Crisis regime and downgrade conviction during Turbulent regime |
| FR-SIG-10 | ML agent shall use per-symbol LightGBM models (class_weight='balanced', Optuna HPO 25 trials) with global fallback for thin data |
| FR-SIG-11 | MA and RSI agents shall use adaptive periods based on vol regime (EWMA span=32): Low <1.5% uses fast periods, High >3.0% uses slow periods |
| FR-SIG-12 | System shall ingest Arabic and English news signals from configured public channels and classify each post (SIGNAL/NEWS/COMMENTARY) with ticker, direction, and price levels extracted |

### 5.2 ETF/ETP Signal Generation (FR-ETFSIG)

| ID | Requirement |
|---|---|
| FR-ETFSIG-1 | System shall generate daily BUY/HOLD/SELL signals for all active instruments in the `instrument` table using `engines/agent_etf_signal.py` |
| FR-ETFSIG-2 | ETF signal shall combine: MA crossover (adaptive), RSI (adaptive), NAV premium/discount (LOCAL_EGX only), 5-day momentum via weighted vote |
| FR-ETFSIG-3 | NAV signal shall return UP when ETF trades at >2% discount to NAV and DOWN when at >3% premium |
| FR-ETFSIG-4 | ETF signals shall be stored in `etf_signals` table (UNIQUE on instrument_id + signal_date), idempotent daily upsert |
| FR-ETFSIG-5 | `GET /api/etf/signals` shall return latest signal per instrument joined with instrument metadata |
| FR-ETFSIG-6 | Track Record page shall display ETF & ETP Signals section with per-instrument signal cards showing all four sub-signals |
| FR-ETFSIG-7 | Pro page shall display ETF signals panel with colored UP/DOWN/HOLD cards, confidence %, RSI value, and NAV premium/discount badge |

### 5.3 Execution Realism Gate (FR-EXEC)

All execution realism logic runs during the CI pipeline. Results are persisted to the database before the Node.js API serves them.

| ID | Requirement |
|---|---|
| FR-EXEC-1 | Every BUY signal shall be evaluated against EGX full round-trip cost: brokerage (0.15%) + stamp duty (0.15%) + FRA fee (0.0125%) + EGX exchange fee (0.0125%) + Misr clearing (0.01%), × 2 legs |
| FR-EXEC-2 | Signals with edge ratio < 3× round-trip cost shall be blocked and logged to `blocked_signals` table |
| FR-EXEC-3 | System shall apply liquidity-tiered slippage: High ADV (>5M EGP/day) = 10 bps; Mid ADV (>1M EGP) = 25 bps; Low ADV = 60 bps |
| FR-EXEC-4 | System shall determine market regime (BULL/NEUTRAL/BEAR) daily; new long positions shall be blocked when regime = BEAR; state persisted to `regime_log` |
| FR-EXEC-5 | System shall model EGX daily ±10% price limits when computing realistic stop prices |
| FR-EXEC-6 | Open positions shall have a trailing stop activating on day 20 at 6% below peak, ratcheting up only, with hard exit on day 45 |
| FR-EXEC-7 | SELL and HOLD signals shall pass through execution gate unchanged |

### 5.4 Dashboard (FR-DASH)

| ID | Requirement |
|---|---|
| FR-DASH-1 | Main dashboard shall display today's consensus signal, Xmore Score, confidence, agent agreement, and sentiment for each stock |
| FR-DASH-2 | Dashboard shall support stock screener filtering by signal, conviction, sector, and minimum confidence |
| FR-DASH-3 | Dashboard shall support full EN/AR language toggle with RTL layout |
| FR-DASH-4 | Dashboard shall support dark and light themes, persisted in localStorage |
| FR-DASH-5 | Dashboard shall display signal-level accuracy by agent and by horizon (D+5, D+10, D+20) |
| FR-DASH-6 | All pages shall be responsive (mobile, tablet, desktop) |
| FR-DASH-7 | Main dashboard shall display a market regime banner (Calm / Turbulent / Crisis) with 30-day BUY/SELL % signal mix and a link to full regime analysis |
| FR-DASH-8 | Pro page shall display a Market Regime stat pill in the header stats row |

### 5.5 Session Sheet (FR-SESSION)

| ID | Requirement |
|---|---|
| FR-SESSION-1 | Session sheet shall display classic daily pivot levels (P, R1, R2, S1, S2) derived from prior session OHLC |
| FR-SESSION-2 | Session sheet shall display 14-day ATR (in EGP) and trend bias (bullish/neutral/bearish) using EMA10/EMA30 crossover |
| FR-SESSION-3 | Session sheet shall display type classification per stock (متاجرة = trading / احتفاظ = holding) with buy guide at S1 |
| FR-SESSION-4 | Authenticated users shall be able to open and close virtual positions from today's BUY signals and track live P&L |

### 5.6 Portfolio & Alerts (FR-PORT)

| ID | Requirement |
|---|---|
| FR-PORT-1 | Users shall be able to create and track virtual stock positions with entry price, quantity, and entry date |
| FR-PORT-2 | System shall compute live cost vs market value and P&L in EGP for all open positions |
| FR-PORT-3 | Users shall be able to set price alerts (above/below threshold) for any EGX stock, up to 20 active alerts |
| FR-PORT-4 | Price alerts shall be evaluated automatically when the user opens the Portfolio tab; triggered alerts shall be marked as fired |

### 5.7 Forecast Portfolios (FR-FORE)

| ID | Requirement |
|---|---|
| FR-FORE-1 | Users shall be able to create named forecast portfolios with up to N stocks and a chosen horizon (1m, 2m, 3m, 6m, 1y, 2y) |
| FR-FORE-2 | System shall generate a per-stock expected return forecast using a pure-JavaScript GBM Monte Carlo engine (no Python dependency) |
| FR-FORE-3 | System shall record daily actual closing prices and overlay them against forecasts on a chart |
| FR-FORE-4 | System shall generate a plain-language narrative describing portfolio phase, gap, and beat count |

### 5.8 Performance & Track Record (FR-PERF)

All performance metrics are pre-computed by the Python pipeline and stored in PostgreSQL.

| ID | Requirement |
|---|---|
| FR-PERF-1 | System shall compute EGX-correct Sharpe ratio using CBE rate (27.25% annual) and 247 trading days |
| FR-PERF-2 | System shall compute Sortino ratio, Calmar ratio, and Information Ratio vs EGX30 |
| FR-PERF-3 | System shall compute max drawdown with peak date, trough date, and recovery status |
| FR-PERF-4 | System shall compute rolling 30-day Sharpe sparkline |
| FR-PERF-5 | Track record page shall be publicly accessible without authentication |
| FR-PERF-6 | Track record shall display: equity curve, KPI strip (30/60/90d rolling windows), per-agent accountability, walk-forward backtest results, live signal feed, signal distribution (BUY/SELL/HOLD 30d), sector accuracy, regime-aware performance table, methodology comparison card, ETF signals section, top stocks by alpha, paginated prediction log |
| FR-PERF-7 | Prediction log shall be exportable as CSV |
| FR-PERF-8 | Walk-forward backtest shall run weekly (every Sunday 09:00 Cairo) for all tracked symbols; results stored in `backtest_results` and `backtest_run_log` tables |
| FR-PERF-9 | Track record shall serve 10+ API endpoints under `/api/track-record/*`: kpis, equity-curve, agents, stocks, backtest, predictions, export, signal-distribution, sector-accuracy, regime-stats, etf-signals |
| FR-PERF-10 | Regime-aware performance section shall show accuracy, win rate, and avg return per regime (Calm / Turbulent / Crisis) |
| FR-PERF-11 | Sector accuracy section shall show win rate and avg return per EGX sector |

### 5.9 Investor Scoring (FR-SCORE)

| ID | Requirement |
|---|---|
| FR-SCORE-1 | System shall compute a composite investor score (0–1): `consensus×0.40 + execution×0.25 + regime×0.20 + momentum×0.15` |
| FR-SCORE-2 | System shall translate to 6 output modes: xmore_native (0–1), standard_100 (0–100), letter_grade (A+→F), stars (1–5), signal_tier (S/A/B/C/D), conviction (HIGH/MEDIUM/LOW) |
| FR-SCORE-3 | All 6 formats and a `meets_threshold` boolean shall be stored in `scored_signals.all_formats` (JSON) at pipeline time |
| FR-SCORE-4 | Dashboard shall provide a mode selector UI |

### 5.10 ETF & Rates (FR-ETF)

| ID | Requirement |
|---|---|
| FR-ETF-1 | System shall fetch and display data for ~13 EGX-listed ETFs (price, NAV, premium/discount, volume) |
| FR-ETF-2 | System shall fetch and display data for global Egypt-focused ETFs (EGPT, FM, FRDM, etc.) via yfinance |
| FR-ETF-3 | System shall display live FX rates: USD/EGP, USD/SAR, SAR/EGP |
| FR-ETF-4 | System shall display live gold prices: 24K, 21K, 18K per gram EGP and Gold Pound EGP |
| FR-ETF-5 | System shall store one FX/gold row per day in `fx_rates_history`, building a 90-day sparkline |
| FR-ETF-6 | ETF browsing tab shall support grid/table view, search by symbol/name, and holdings modal (snapshot date, constituents, weights) |
| FR-ETF-7 | ETF signal generation shall run daily as part of `run_agents.py` pipeline (non-fatal; skipped if instrument table missing) |

### 5.11 AI Assistant & RAG (FR-RAG)

| ID | Requirement |
|---|---|
| FR-RAG-1 | Market assistant shall inject live context into every prompt: prices, consensus signals, sentiment, ETF prices+NAV+AUM+signals, current market regime (+ 5-day history), 30-day signal distribution, walk-forward backtest summary, agent accuracy leaderboard, user portfolio (when logged in) |
| FR-RAG-2 | Uploaded PDF documents (ETF factsheets, market reports) shall be chunked and embedded via Gemini `text-embedding-004` |
| FR-RAG-3 | Market assistant shall perform semantic search over embedded documents for relevant questions |
| FR-RAG-4 | Macro brief shall use Gemini grounded web search to produce a structured real-time Egypt macro summary with web citations |
| FR-RAG-5 | Assistant shall have full EGX market knowledge: 190+ stocks, trading hours, indices, symbol format, regulator, Xmore methodology (walk-forward validation, 4-layer consensus, regime gating, confidence thresholding) |
| FR-RAG-6 | News RAG chunks (`news_rag_chunks`) shall be included in semantic search with recency-weighted scoring |
| FR-RAG-7 | Custom news source articles shall be included in the assistant's news context |

### 5.12 Authentication & Access Control (FR-AUTH)

| ID | Requirement |
|---|---|
| FR-AUTH-1 | Users shall be able to register and log in with email and password |
| FR-AUTH-2 | Session tokens shall be JWT stored in HTTP-only cookies |
| FR-AUTH-3 | Portfolio, alerts, and forecast portfolios shall be per-user, private |
| FR-AUTH-4 | Core signal data, performance metrics, and track record shall be accessible without authentication |
| FR-AUTH-5 | Admin panel shall require a separate admin credential |

---

## 6. Non-Functional Requirements

### 6.1 Availability
- Dashboard shall be available 24/7; planned downtime only during EGX non-trading hours (Friday–Saturday)
- Signal pipeline shall complete by 09:00 Cairo time on each trading day

### 6.2 Performance
- API response time for standard signal endpoints: < 500 ms at p95 (all results pre-computed)
- Dashboard initial load: < 3 seconds on a 4G connection
- Database queries shall not perform full table scans on tables > 10,000 rows (indexes required)

### 6.3 Scalability
- System shall support concurrent access by up to 500 simultaneous users without degradation
- ETF pipeline shall complete within 15 minutes for all instruments

### 6.4 Reliability
- GitHub Actions pipeline failures shall not corrupt existing data; each job is idempotent
- All database writes shall use upsert (INSERT OR REPLACE / ON CONFLICT DO UPDATE)
- PostgreSQL transaction errors shall be isolated per-row using SAVEPOINT/ROLLBACK TO SAVEPOINT
- If execution realism, ETF signals, or scoring modules fail, the core pipeline continues (fail-open design)

### 6.5 Internationalisation
- All user-facing strings shall exist in both English and Arabic
- Arabic layout shall use RTL direction and appropriate CSS
- Date display shall account for EGX timezone (Africa/Cairo, UTC+2/+3 DST)

### 6.6 Maintainability
- New pipeline features added as separate modules; existing agent files not modified
- New database tables added to both `database.py` and `web-ui/init-db.js`
- All constants centralised in configuration files

---

## 7. System Architecture

### 7.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                          │
│  (7 scheduled cron jobs — Sun–Thu + weekly)                  │
│                                                              │
│  PYTHON EXECUTION BOUNDARY — all Python runs here           │
│  ─────────────────────────────────────────────────────────  │
│  run_agents.py                                               │
│    → Telegram news ingestion (non-fatal)                     │
│    → 6 AI agents → consensus_engine.py (4-layer pipeline)   │
│    → Confidence gating (< 60% → HOLD)                       │
│    → Regime gate (Crisis blocks UP; Turbulent downgrades)    │
│    → apply_execution_realism() [friction gate]               │
│    → _populate_scored_signals() [6-mode scoring]             │
│    → agent_etf_signal.run_etf_signals() [ETF predictions]    │
│    → evaluate_performance.py [D+1, D+5 outcomes]            │
│  run_backtest.py (weekly Sunday)                             │
│    → walk_forward_backtest.py [90d/20d/10d rolling]          │
│    → 6 agents evaluated out-of-sample                        │
│  database.py writes to PostgreSQL                            │
└──────────────────────┬──────────────────────────────────────┘
                       │ ALL results pre-computed and written
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                PostgreSQL (Render.com)                        │
│  40+ tables — signals, prices, news, performance,           │
│  ETF, portfolio, RAG, scoring, execution audit,              │
│  etf_signals, backtest_results, backtest_run_log,           │
│  system_config, regime_log, news_rag_chunks                  │
│                                                              │
│  API boundary: Node.js reads; Python writes                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ SELECT only (no Python at request time)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          Node.js / Express API Server (Render)               │
│  web-ui/server.js — 13 route modules                        │
│  Routes: auth, stocks, trades, watchlist, briefing,         │
│  performance, track-record, etf, rag, scoring,              │
│  timemachine, portfolioForecasts, admin                      │
│  SQLite wrapper (local dev) / pg Pool (production)          │
└──────────────────────┬──────────────────────────────────────┘
                       │ serves
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Vanilla JS Frontend (8 pages)                   │
│  / (app.js)  ·  /pro (pro.js)  ·  /session (session.js)    │
│  /track-record  ·  /timemachine  ·  /landing  ·  /docs      │
│  /admin — bilingual EN/AR, RTL, dark/light mode             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Deployment

| Component | Platform | Notes |
|---|---|---|
| Web server + API | Render.com (Node.js service) | Auto-deploys on push to `main` |
| PostgreSQL | Render.com managed PostgreSQL | Schema initialised by `init-db.js` on each deploy |
| Python pipeline | GitHub Actions (`ubuntu-latest`) | 7 cron jobs; connects to production PostgreSQL via `DATABASE_URL` |
| Static assets | Served by Express | `express.static()` from `web-ui/public/` |

### 7.3 Four-Layer Consensus Pipeline

```
Layer 1: Agent Vote
  ML (LightGBM per-symbol, Optuna HPO)
  MA (adaptive short/long MA crossover)
  RSI (adaptive period, oversold/overbought)
  Volume (unusual activity detection)
  Gemini Sentiment (recency-decayed news analysis)
  Risk (volatility, GARCH forecast, position limits)
            ↓
Layer 2: Weighted Average
  Accuracy-adjusted agent weights (agent_performance_daily)
  Confidence gating: max(proba) < 60% → HOLD
            ↓
Layer 3: Risk Filter
  Execution realism (costs, slippage, trailing stops)
  Investor composite score (6-mode output)
            ↓
Layer 4: Regime Gate
  HMM market state (Calm / Turbulent / Crisis)
  Crisis → block all UP signals
  Turbulent → downgrade conviction level
```

### 7.4 Pre-computation Pattern (Critical)

Because Python cannot run on Render at request time, every calculated value must be pre-computed during a pipeline run and written to the database. The API is a thin read layer guaranteeing < 500 ms responses regardless of model complexity.

---

## 8. Data Requirements

### 8.1 Core Tables (selected)

| Table | Purpose | Key columns |
|---|---|---|
| `prices` | Daily OHLCV per symbol | symbol, date, open, high, low, close, volume |
| `consensus_results` | Daily consensus signal per symbol | symbol, prediction_date, final_signal, xmore_score, confidence, conviction |
| `trade_recommendations` | Enriched signals with execution data | symbol, recommendation_date, prediction, confidence, edge_ratio, execution_approved, alpha_1d, alpha_5d, trend_ar, buy_guide, pivot, r1, r2, s1, s2 |
| `scored_signals` | 6-mode composite scores | symbol, signal_date, composite_score, all_formats (JSON), meets_threshold |
| `blocked_signals` | Audit log of rejected BUY signals | ticker, signal_date, block_reason, regime_at_block |
| `regime_log` | Daily market regime history | date, regime, egx30_price, ma20, distance_pct |
| `backtest_results` | Weekly walk-forward results | symbol, agent_name, run_date, accuracy, directional_accuracy, signal_pnl_pct |
| `backtest_run_log` | Walk-forward run summary | run_date, symbols_tested, windows_run, overall_accuracy, agent_summaries_json |
| `etf_signals` | Daily ETF/ETP technical signals | instrument_id, symbol, signal_date, signal, confidence, ma_signal, rsi_signal, nav_signal, momentum_signal, nav_premium_pct |
| `instrument` | ETF/ETP master data | symbol, name, type, region, issuer, currency, is_active |
| `etf_price_daily` | Daily ETF OHLCV | instrument_id, trade_date, close_price, volume |
| `etf_nav` | Daily ETF NAV values | instrument_id, nav_date, nav_unit |
| `etf_fund_volume` | ETF AUM and subscriptions | instrument_id, asof_date, aum, net_subscriptions_units |
| `news_rag_chunks` | Semantically embedded news | title, content, embedding, published_at, source_name |
| `system_config` | Key-value config store (Telegram session, etc.) | key PK, value, updated_at |
| `user_positions` | Virtual portfolio positions | user_id, symbol, entry_price, quantity, return_pct |
| `fx_rates_history` | Daily FX and gold rates | date, USD_EGP, XAU_USD, GOLD_24K_EGP_G |
| `rag_chunks` | Embedded document chunks | doc_id, chunk_text, embedding (JSON) |

### 8.2 Data Retention

- Price history: indefinite (append-only)
- News: indefinite (headline + sentiment)
- Signal evaluations: indefinite (audit trail)
- Blocked signals: indefinite (never delete — compliance)
- ETF signals: indefinite (daily append)
- RAG embeddings: retained until document deleted by admin

### 8.3 Data Sources

| Source | Data | Frequency |
|---|---|---|
| yfinance | EGX stock OHLCV, ETF prices, EGX30 index, macro (Brent, EEM) | Daily + intraday |
| EGX live scraper (`http://41.33.162.236/egs4/`) | Real-time EGX prices | Intraday (primary) |
| Mubasher (scraper) | EGX-listed ETF prices, NAV, volume | Daily |
| NewsAPI / Finnhub | Market headlines for sentiment | Intraday (3×/day) |
| Public EGX channels | Arabic/English market news and signals | Intraday (via configured ingestion) |
| CBE (cbe.org.eg) | USD/EGP official rate | Daily |
| open.er-api.com / fallbacks | FX rates + gold | On-demand (Node.js) |
| Google Gemini 2.5 Flash | Sentiment, RAG, macro brief, market assistant | On-demand (Node.js + Python pipeline) |

---

## 9. Integrations & External Dependencies

| Service | Purpose | Credential | Caller |
|---|---|---|---|
| **Google Gemini API** | LLM agent, sentiment, RAG embeddings, macro brief, market assistant | `GOOGLE_API_KEY` | Both |
| **NewsAPI** | Market news headlines | `NEWS_API_KEY` | Python (CI) |
| **Finnhub** | Supplementary financial data | `FINNHUB_API_KEY` | Python (CI) |
| **yfinance** | EGX stock prices, ETF prices, EGX30 index, macro | — | Python (CI) |
| **EGX live scraper** | Real-time EGX prices (primary) | — | Python (CI) |
| **Mubasher** | EGX ETF NAV and prices | — | Python (CI) |
| **Public news channels** | Arabic/English EGX market signal ingestion | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Python (CI) |
| **CBE / open.er-api.com** | FX rates — CBE official primary, fallback chain | — | Python (CI) + Node.js |
| **Render.com** | Hosting, PostgreSQL, managed TLS | Render account | — |
| **GitHub Actions** | Scheduled pipeline CI/CD | `DATABASE_URL` + all secrets | — |

---

## 10. Automated Pipeline

### 10.1 Scheduled Jobs

| Job | Cron (UTC) | Cairo Time | Days | Purpose |
|---|---|---|---|---|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | 09:00–14:00 | Sun–Thu | Live price snapshots during trading session |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | 09:00, 11:00, 13:00 | Sun–Thu | Refresh news + sentiment 3× during session |
| `post-market-pipeline` | `30 12 * * 0-4` | 14:30 | Sun–Thu | Store closing prices, trigger evaluation |
| `egx-daily-snapshot` | `0 14 * * 0-4` | 16:00 | Sun–Thu | Final daily data snapshot |
| `daily-pipeline` | `0 22 * * 0-5` | 00:00+1 | Sun–Fri | Telegram ingestion → 6 agents → consensus → execution gate → ETF signals → scoring |
| `catchup-evaluation` | `0 6,12,18 * * *` | 3× daily | Daily | Resolve pending D+1/D+5 outcomes + `evaluate_performance.py` |
| `weekly-backtest` | `0 7 * * 0` | 09:00 | Sunday | Walk-forward backtest all symbols across all 6 agents |

### 10.2 Pipeline Design Principles

- **Idempotent** — all inserts use upsert; re-running produces identical state
- **Fail-safe** — individual row errors do not abort the batch (SAVEPOINT isolation)
- **Fail-open** — optional modules (ETF signals, Telegram ingestion, scoring) wrapped in try/except; partial results better than zero
- **Audit-logged** — blocked signals, regime state, ETF signals, and evaluation outcomes all persisted
- **No manual steps** — zero human intervention required for normal operation
- **Pre-computation first** — every value the API needs written to PostgreSQL during pipeline, not calculated on demand

---

## 11. Security Requirements

| Requirement | Implementation |
|---|---|
| Authentication | JWT in HTTP-only cookie (prevents XSS token theft) |
| Password storage | Bcrypt hashing (12 rounds) — never stored in plain text |
| API secrets | Environment variables only; never in source code or logs |
| SQL injection prevention | Parameterised queries throughout |
| Admin access | Separate credential checked against `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars |
| CORS | Configured to restrict cross-origin requests in production |
| Input validation | All user-supplied parameters parsed and bounded before use |
| XSS prevention | `textContent` for error output; global `escapeHtml()` for all dynamic HTML |
| Rate limiting | Applied on auth endpoints |

---

## 12. Performance & Metrics

### 12.1 Signal Quality KPIs

| Metric | Definition | Calibration |
|---|---|---|
| Directional accuracy | % of signals where predicted direction = actual direction at D+1 | Evaluated daily |
| Alpha (D+1) | Signal return − EGX30 return at D+1 | Stored in `alpha_1d` |
| Alpha (D+5) | Signal return − EGX30 return at D+5 | Stored in `alpha_5d` |
| Sharpe ratio | `(mean_excess_return / std_return) × sqrt(247)` | CBE 27.25%; 247 EGX days |
| Sortino ratio | `(mean_excess_return / downside_std) × sqrt(247)` | Downside-only |
| Calmar ratio | `annualised_return / abs(max_drawdown)` | Min 20 data points |
| Information ratio | `mean_alpha / std_alpha` | vs EGX30 |
| Max drawdown | Peak-to-trough equity decline | With recovery date |
| Walk-forward accuracy | Out-of-sample directional accuracy per agent | 90d train / 20d test / 10d step |

### 12.2 ETF Signal KPIs

| Metric | Definition |
|---|---|
| ETF signal distribution | BUY/HOLD/SELL counts per 30-day window |
| NAV premium/discount | (Price − NAV) / NAV × 100 per fund |
| Signal confidence | Weighted vote score (0–1) |

---

## 13. Constraints & Assumptions

### 13.1 Python on Render — Architectural Constraint

**Constraint:** Render.com hosts Xmore as a Node.js (`env: node`) service. Python cannot be executed at request time.

**Implication:** Every value the API returns must already exist in PostgreSQL. The execution realism layer, ETF signal engine, investor scoring system, performance metrics, and regime detection all run in GitHub Actions CI — results are pre-stored. The API reads stored rows; it never calls Python.

**What this is NOT a limitation for:**

| Feature | Works fine because… |
|---|---|
| Gemini market assistant / macro brief | Gemini API called directly from Node.js |
| FX & gold rates | open.er-api.com called from Node.js |
| GBM Monte Carlo forecast (Time Machine) | Pure JavaScript in `forecastEngine.js` |
| Signal display | Pre-computed rows |
| ETF signal cards | Pre-computed `etf_signals` rows |

### 13.2 Other Constraints

- **EGX trading calendar**: Sunday–Thursday; Friday and Saturday are non-trading days
- **EGX daily price limit**: ±10% maximum move per session; execution layer accounts for this
- **Render.com free tier**: Auto-spins down after inactivity; 30–60s cold-start on first request
- **yfinance dependency**: EGX data quality occasionally stale; pipeline handles gracefully
- **Gemini API quotas**: Rate limits; sentiment generation includes retry logic
- **Telegram API**: Session must be bootstrapped once interactively (`--setup` flag); then persisted in `system_config` table

### 13.3 Assumptions

- Egypt CBE overnight deposit rate (27.25%) reviewed quarterly and updated in configuration
- EGX trading days per year (247) reviewed annually
- EGX30 index (`^CASE30`) used as performance benchmark throughout
- Historical simulation data is treated as transparent supplementary data, tagged `SIM` in prediction log

---

## 14. Architectural Decisions & Trade-offs

### 14.1 Pre-computation vs On-demand Python

**Decision:** All Python calculations are batch/scheduled, never request-time.

**Rationale:** Render.com `env: node` is a hard platform constraint. Pre-computing ensures API responses are always < 500 ms regardless of model complexity. A 6-agent consensus run for 190 stocks with execution scoring would take 10–30 seconds on demand; from the database it takes < 50 ms.

### 14.2 SQLite Local / PostgreSQL Production Dual-mode

**Decision:** `database.py` and `server.js` detect `DATABASE_URL` to switch backends automatically.

**Constraint:** Use the `.all()/.get()/.run()` wrapper only — never `.query()` which only works with pg.

### 14.3 No Agent Modification Policy

**Decision:** New pipeline features added as separate modules, never by modifying the 6 agent files.

**Rationale:** Agents are independently testable black boxes. Cross-cutting concerns (costs, regime) belong downstream.

### 14.4 Walk-Forward Over Simple Backtest

**Decision:** The system uses rolling walk-forward validation (90d train / 20d test / 10d step) rather than a single in-sample backtest.

**Rationale:** In-sample backtests can reflect memorised patterns rather than genuine predictive edge. Walk-forward tests the model on data it has never seen — the institutional standard. Results shown on the Track Record page with a methodology comparison card explaining the difference to users.

### 14.5 JavaScript-only Frontend

**Decision:** No framework (React/Vue/Svelte); vanilla JS with ES6 modules.

**Rationale:** Reduces build complexity, eliminates hydration overhead. Given the project scope (pre-market signals, tabular data), framework overhead is not justified.

### 14.6 ETF Signal Architecture

**Decision:** ETF signals use a purpose-built lightweight technical engine rather than the full 6-agent ML pipeline.

**Rationale:** ETFs have lower individual volatility and clear NAV anchors that stocks lack. MA + RSI + NAV premium/discount is a well-understood, interpretable set of signals for fund instruments. Per-symbol LightGBM models would require years of per-ETF training data that doesn't yet exist. The engine is designed to be upgraded incrementally as ETF price history accumulates.

---

## 15. Roadmap

### 15.1 Near-term
- [ ] ETF ML models (LightGBM per-instrument) once sufficient price history accumulates
- [ ] Real-time intraday signal updates (SSE feed from Node.js)
- [ ] Push notifications (email / app) when a signal changes from HOLD to BUY
- [ ] Brokerage API integration (direct order placement)
- [ ] Render Background Worker for on-demand Python scoring

### 15.2 Medium-term
- [ ] Paid Pro tier with advanced screener and direct API access key
- [ ] Portfolio optimiser (mean-variance, EGX constraints)
- [ ] Mobile app (React Native, sharing the same API)
- [ ] Expansion to ADX (Abu Dhabi) and Tadawul (Saudi)
- [ ] EGX derivatives signals when the exchange enables them

### 15.3 Architectural Improvements
- [ ] Stream evaluation: compute D+1 outcomes at 14:30 Cairo (post-market) rather than waiting for catchup cron
- [ ] On-demand regime re-check via stateless Python microservice (FastAPI on worker dyno)
- [ ] Pre-compute performance metrics during `daily-pipeline` to have them ready for overnight users

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
| **Confidence Gating** | Dropping signals to HOLD when max(agent probability) < 60% |
| **Composite Score** | Weighted combination of consensus (40%), execution (25%), regime (20%), momentum (15%) |
| **Consensus Signal** | BUY / HOLD / SELL derived from majority-weighted agent vote through 4-layer pipeline |
| **D+1 / D+5** | Evaluation horizons — 1 or 5 trading days after signal date |
| **EGX** | Egyptian Exchange — the primary stock exchange of Egypt |
| **EGX30** | The EGX blue-chip index of the 30 most liquid Egyptian stocks |
| **Edge Ratio** | Signal expected return ÷ round-trip transaction cost |
| **HMM** | Hidden Markov Model — used for market regime detection (Calm / Turbulent / Crisis) |
| **IR** | Information Ratio — consistency of alpha generation relative to its volatility |
| **MDD** | Maximum Drawdown — largest peak-to-trough decline in the equity curve |
| **NAV** | Net Asset Value — per-unit fair value of an ETF |
| **NAV Premium/Discount** | (ETF price − NAV) / NAV × 100; negative = discount (potential buy signal) |
| **Pivot Levels** | Support/resistance levels calculated from prior session's High, Low, and Close |
| **Pre-computation Pattern** | All Python metrics computed during CI pipeline jobs and stored in PostgreSQL; Node.js API reads stored values only |
| **RAG** | Retrieval-Augmented Generation — using embedded document chunks to ground AI answers |
| **Regime** | Market state (Calm / Turbulent / Crisis) determined by HMM on EGX30 price history |
| **Round-trip cost** | Total transaction cost for entering and exiting a position (both legs) |
| **Sharpe Ratio** | Risk-adjusted excess return: `(mean_return − RF) / std_return × sqrt(trading_days)` |
| **SIM** | Simulated — tag applied to historical backfill predictions, distinct from live signals |
| **Sortino Ratio** | Like Sharpe but only penalises downside volatility |
| **Trailing Stop** | A stop-loss that only moves in the direction of profit, never against it |
| **Walk-Forward Validation** | Rolling 90d-train / 20d-test / 10d-step out-of-sample backtesting; the institutional standard |
| **Xmore Score** | Proprietary 0–100 bullishness composite across all agent votes |

---

*Xmore — AI Stock & Fund Intelligence for the Egyptian Exchange*
*Version 1.4 · March 2026*
