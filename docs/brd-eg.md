# Business Requirements Document — Xmore (EGX)
**Version:** 1.7 | **Date:** April 2026 | **Status:** Active

---

## 1. Executive Summary

Xmore is an AI-powered stock trading assistant for the Egyptian Exchange (EGX). It delivers daily multi-agent predictions, walk-forward backtested strategies, and a real-time web dashboard — giving retail investors systematic, data-driven insight into EGX-listed equities.

**Live deployment:** https://xmore-project.onrender.com

---

## 2. Problem Statement

Egyptian retail investors lack affordable, systematic tools for EGX equity analysis. Professional-grade signal generation, backtesting, and position sizing are inaccessible or cost-prohibitive. Xmore fills this gap with an automated pipeline that runs daily on GitHub Actions and surfaces results through a mobile-friendly web UI.

---

## 3. Target Market

- Egyptian retail and semi-professional equity traders
- EGX-listed stocks (.CA suffix)
- Primary index benchmark: EGX30

---

## 4. Core Objectives

| # | Objective |
|---|-----------|
| 1 | Generate daily buy/sell/hold signals for EGX equities using a 6-agent AI pipeline |
| 2 | Provide walk-forward backtested performance metrics with friction costs |
| 3 | Size positions using Kelly Criterion with shrinkage and adaptive weighting |
| 4 | Surface signals, portfolio, and analytics through a responsive web dashboard |
| 5 | Run fully automated on GitHub Actions with zero manual intervention |

---

## 5. Business Model

- Free-tier hosted on Render.com (web service + PostgreSQL)
- GitHub Actions free tier for automation (~400 pipeline-minutes/month)
- No subscription or monetisation currently; internal research tool

---

## 6. Data Sources

| Source | Usage |
|--------|-------|
| EGX official / Mubasher | Intraday + EOD price data (.CA symbols) |
| News APIs (NewsAPI, Marketaux) | Sentiment & headline extraction |
| Telegram channels | Arabic-language market sentiment |
| Finnhub | Supplementary fundamentals |
| Google Gemini (gemini-2.5-flash) | AI agent reasoning |
| EODHD | ETF price data |

---

## 7. System Architecture

### 7.1 Infrastructure

| Component | Platform | Details |
|-----------|----------|---------|
| Web dashboard | Render.com web service | Node.js / Express |
| Database | Render.com PostgreSQL | `xmore-db` |
| Automation | GitHub Actions | `crassdart85/xmore-v2` |
| Schema init | `web-ui/init-db.js` | Runs in `buildCommand` |

### 7.2 Key Source Files

| File | Role |
|------|------|
| `web-ui/server.js` | Express API server |
| `web-ui/init-db.js` | PostgreSQL schema + seed (`safeDDL` pattern) |
| `web-ui/routes/trades.js` | Trade recs, portfolio, positions, session-sheet |
| `web-ui/routes/screening.js` | Screening engine API |
| `web-ui/routes/rag.js` | RAG semantic search |
| `web-ui/routes/etf.js` | ETF analytics |
| `web-ui/public/app.js` | Frontend (~4000+ lines) |
| `web-ui/public/portfolioForecasts.js` | Forecast Portfolios tab |
| `engines/screening_engine.py` | Stock screening backend |
| `engines/signal_enrichment.py` | Signal enrichment pipeline |
| `engines/kelly_allocator.py` | Kelly position sizing |
| `engines/portfolio_rebalancer.py` | Portfolio rebalancing |
| `engines/backtest_friction.py` | Friction-aware backtest helper |
| `engines/pivot_engine.py` | Pivot levels, ATR, candlestick patterns |
| `engines/backtest.py` | Walk-forward backtest (`--save` upserts to `backtest_results`) |
| `engines/agent_weights.py` | Softmax dynamic agent weights (T=2.0, floor 5%) + audit log |
| `engines/event_detector.py` | News event detection → targeted sentiment refresh |
| `engines/job_locks.py` | Advisory TTL-based pipeline locking |
| `engines/macro_data.py` | MacroDataProvider: CBE rate, USD/EGP, CPI, GDP → composite risk score |
| `web-ui/services/openbbMcpBridge.js` | MCP bridge: live quotes + macro context for RAG chat |
| `openbb_egx/` | OpenBB-compatible EGX data provider (Pydantic v2, async TradingView + yfinance) |
| `backfill_history.py` | Bulk historical price backfill |

---

## 8. AI Pipeline

### 8.1 Six-Agent Architecture

Each trading day the pipeline runs six specialised agents in sequence:

| Agent | Role |
|-------|------|
| Fundamentals | P/E, EPS, revenue trends |
| Technical | RSI, MACD, Bollinger, pivot levels |
| Sentiment | News + Telegram headlines scoring |
| Macro | EGP/USD rate, CBE rate, sector flows |
| Risk | Volatility, ATR, stop-loss calibration |
| Orchestrator | Synthesises all agent outputs → final signal |

### 8.2 Signal Output

- **Signal types:** BUY / SELL / HOLD
- **Xmore Score:** 0–100 composite conviction score
- **Conviction gate:** LOW conviction BUY (score < 40) is discarded before storage
- **Consensus:** multi-day rolling consensus across agent outputs

### 8.3 Market Regime Detection

`_detect_market_regime()` uses MA/volatility analysis (not HMM). Result written to `regime_log` after each detection run.

### 8.4 Dynamic Agent Weighting (April 2026)

`engines/agent_weights.py` replaces static equal weights with softmax-based dynamic weights computed from recent 30-day directional accuracy. Temperature=2.0, floor=5%. Weight history logged to `agent_weights_log` table. Falls back to equal weights when insufficient evaluation data exists.

### 8.5 Regime Feedback into Agents (April 2026)

`engines/regime_model.py` `get_current_regime()` returns bull/bear/high_vol labels. `REGIME_SIGNAL_MODIFIERS` in `run_agents.py` applies per-regime bias adjustments and threshold gates before consensus:
- **Bull**: +5% confidence bias to UP signals, UP threshold lowered to 55%
- **Bear**: +5% confidence bias to DOWN signals, DOWN threshold lowered to 55%
- **High Vol**: confidence dampened by 10%, directional thresholds raised to 70%

### 8.6 Event-Triggered Sentiment Refresh (April 2026)

`engines/event_detector.py` (`EGXEventDetector`) scans recent news before the agent pipeline runs. Detects:
- CBE rate decisions (affects all stocks)
- Earnings announcements (affects mentioned symbols)
- Regulatory actions (FRA suspensions, delistings)
- EGX30 index rebalances
- Opening price gaps >3%

Triggers targeted `collect_sentiment()` for affected symbols before predictions.

### 8.7 Calibrated Evaluation Metrics (April 2026)

`evaluate.py` now computes multi-metric scoring per prediction: magnitude score, Brier calibration, signal strength, and actual return. `evaluate_performance.py` computes Information Coefficient (IC) via Spearman rank correlation. Exposed via `/api/track-record/summary`.

### 8.8 OpenBB MCP Bridge (April 2026)

`web-ui/services/openbbMcpBridge.js` enriches the RAG chat assistant with live market data when an OpenBB API server is running. Extracts EGX symbols from user queries, fetches live quotes and macro context. A "Live data" badge (EN/AR) is shown on enriched responses in the assistant widget.

---

## 9. Position Sizing — Kelly Criterion

`engines/kelly_allocator.py`:

- Full Kelly fraction computed from win rate + average win/loss ratio
- **Adaptive weighting:** blends 30d / 90d win rate with alpha, sample-size shrinkage, and drift penalties
- Half-Kelly applied as default for risk management
- Output fed directly into live pipeline via `run_agents.py`

---

## 10. Backtesting

`engines/backtest.py` — walk-forward methodology:

- **Friction costs** included via `engines/backtest_friction.py`
- EGX brokerage costs, taxes, and spread estimated per trade
- Walk-forward folds: rolling train/test windows
- Results stored in `backtest_results` table via `--save` flag
- **Performance reporting is net-of-transaction-cost** throughout

---

## 11. GitHub Actions Schedule (UTC)

| Job | Cron | Notes |
|-----|------|-------|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | Prices only — no schema init |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | |
| `post-market-pipeline` | `30 12 * * 0-4` | 90m timeout |
| `egx-daily-snapshot` | `0 14 * * 0-4` | |
| `daily-pipeline` | `0 22 * * 0-5` | 60m timeout |
| `catchup-evaluation` | `0 6,18 * * *` + `15 12 * * *` | 30m timeout; 12:15 staggers past price-update |
| `etf-egx-all` | `30 13 * * 0-4` | |
| `etf-global-prices` | `30 21 * * 1-5` | |
| `etf-rag-embedding` | `15 6,10,14,20 * * *` | 4×/day |
| `weekly-backtest` | `0 7 * * 0` | |

All schema init steps: `timeout-minutes: 2` + `continue-on-error: true`.
`intraday-price-update` has **no** schema init step (removed — deadlock risk).

---

## 12. Web Dashboard Features

### 12.1 Navigation Structure

| Section | Description |
|---------|-------------|
| Home / Briefing | Daily market briefing with signal action cards |
| Signals | Full signal table with filters, conviction scores |
| Watchlist / Consensus | Multi-day consensus view per ticker |
| Portfolio | Position tracker with EGP P&L, Kelly-sized allocations |
| Track Record | Live performance vs EGX30 benchmark |
| Screening | Multi-factor stock screener |
| Forecast Portfolios | AI-projected portfolio outcomes |
| ETF | Egyptian and global ETF analytics |
| Rates | USD/EGP FX rate + gold price history |
| Session Sheet | Intraday session-level trade log |
| Pro | Advanced analytics, EGX30 chart, macro indicators |
| RAG / Docs | Semantic search over knowledge base |
| Time Machine | Hypothetical historical portfolio simulator |

### 12.2 UI Conventions

- **Header:** All pages use `<header class="x-topbar x-topbar--dark">` with unified nav links (Home, Track Record, Pro, Session, Docs)
- **Mobile:** hamburger pattern `id="<Page>MobileMenuBtn"` / `id="<Page>MobileMenuDropdown"`
- **Language:** EN + AR (Arabic RTL supported throughout)
- **Currency:** EGP throughout; Rates tab shows USD/EGP + Gold EGP/gram
- **Intelligence Pulse:** collapsible sidebar widget; state persists via `localStorage` key `intelligencePulseCollapsed`

### 12.3 AI Assistant Widget

`web-ui/public/assistant-widget.js/css` — embedded chat assistant with topic aliases for quick navigation. Powered by Gemini.

---

## 13. Data Quality & Freshness

- **Change Intelligence:** `/api/intelligence/changes` — signal, forecast, macro deltas
- **Freshness & Drift:** `/api/intelligence/quality`
- **Conviction gate:** prevents low-quality signals from polluting the database
- **Performance is net-of-transaction-cost** — track record and performance routes report net metrics only

---

## 14. Security & Operations

### 14.1 Environment Secrets (GitHub + Render)

`DATABASE_URL`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `GOOGLE_API_KEY`, `JWT_SECRET`, `EODHD_API_KEY`, `MARKETAUX_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`

### 14.2 Auth Pattern

`authMiddleware` sets `req.userId` (not `req.user.userId`). JWT-based session auth.

### 14.3 Claude Code Hooks (Local Dev — March 2026)

Configured in `.claude/settings.json` + `.claude/hooks/`:

| Hook | Event | Purpose |
|------|-------|---------|
| `check-syntax.js` | PostToolUse (Edit/Write) | Runs `node --check` / `python -m py_compile` immediately after every file edit. Catches `??`→`?` corruption. Exit 1 = surfaces error. |
| `guard-bash.js` | PreToolUse (Bash) | Blocks: force-push to main/master, `git reset --hard` to non-HEAD, bypassing git hooks. Exit 2 = blocks. |
| `pre-compact.js` | PreCompact | Logs pre-compaction summary to `.claude/compact-log.txt` (async). |

---

## 15. Known Issues & Constraints

| Issue | Mitigation |
|-------|-----------|
| `??`/`\|\|`→`?` JS corruption (full-page blank) | `node --check` via PostToolUse hook; `portfolioForecasts.js` fixed Mar 2026 |
| `pd.read_sql()` deadlock with psycopg2 | Use `cursor.execute()` + `fetchall()` + `pd.DataFrame` pattern |
| `CREATE INDEX` deadlock in `database.py` | Use `_safe_create_index(cursor, sql)` — never bare `cursor.execute` |
| Render "No open ports detected" | `init-db.js` must be in `buildCommand`, not `startCommand` |
| Mubasher hangs | Circuit breaker: 3 timeouts → skip; 5s timeout, 0.5s sleep |
| Gemini 404 on deprecated models | Use `gemini-2.5-flash` + `text-embedding-005` |
| `authMiddleware` 500 errors | Always use `req.userId`, never `req.user.userId` |
| Render free tier (400 pipeline-min/month) | Resets 1st of each month |

---

## 16. Database Patterns

### 16.1 DDL (init-db.js)

All DDL uses `safeDDL(db, sql, timeoutMs)` transaction wrapper with `SET LOCAL lock_timeout='5s'`:
- Indexes: `safeCreateIndex(db, sql)` — 120s timeout
- Columns: `safeAddColumn(db, sql)` — 10s timeout
- Global session: `lock_timeout=5s`, `statement_timeout=0`
- Disable `statement_timeout` before large seed INSERTs

### 16.2 New Tables

New DB tables must be added to **both**:
1. `database.py` `create_tables()` — use `{auto_id}` f-string (not `AUTOINCREMENT`)
2. `web-ui/init-db.js` — use `SERIAL PRIMARY KEY`; wrap DDL in `safeDDL`

**Tables added April 2026:**
- `agent_weights_log` — softmax weight audit trail (migration 013)
- `macro_indicators` — cached macro data: CBE rate, USD/EGP, CPI, GDP
- `job_locks` — advisory pipeline locking (migration 015)
- New columns on `evaluations`: `magnitude_score`, `calibration_score`, `signal_strength`, `actual_return` (migration 014)
- New column on `predictions`: `confidence_score` (migration 013)

### 16.3 Server.js DB Wrapper

Use `.all()` / `.get()` / `.run()` only — never `.query()`.

### 16.4 News Aggregator INSERTs

Each INSERT in `news_aggregator.py` must use `SAVEPOINT intel_insert` / `ROLLBACK TO SAVEPOINT` for Postgres compatibility.

---

## 17. Deployment Checklist

- [ ] `buildCommand: cd web-ui && npm install && node init-db.js`
- [ ] `startCommand: node server.js`
- [ ] All secrets configured in Render dashboard
- [ ] GitHub Actions secrets match Render env vars
- [ ] `intraday-price-update` job has NO schema init step
- [ ] All other schema init steps have `timeout-minutes: 2` + `continue-on-error: true`

---

## 18. Signal Quality & Presentation Fixes (April 5, 2026)

Three production issues surfaced after the April 3–4 quality-gate rollout produced a 10-day evaluation sample with misleading headline metrics.

### 18.1 Horizon-scaled Tier 2 cost gate

**Problem:** The cost gate in `run_agents.py` compared a **1-day ATR%** to a **5-day hold cost+profit threshold** (2.0 %). Because the typical EGX bluechip daily ATR is 1.0–1.8 %, every directional signal was forced to HOLD, producing a dashboard of all-HOLD with 0.00 % expected edge.

**Fix:** Scale 1-day ATR% by √5 to approximate the 5-day expected move, then compare against the threshold:

```
5d_expected_move = ATR_1d × √5
gate: 5d_expected_move < (round_trip_cost 0.5 % + min_net_profit 1.0 %) = 1.5 % → HOLD
```

- COMI.CA (ATR 1.2 %): 5d move 2.68 % → **PASS**
- EFIH.CA (ATR 0.9 %): 5d move 2.01 % → **PASS**
- Previously all such stocks were killed.

### 18.2 Market-aware data-freshness warnings

**Problem:** On Fri/Sat the `/api/intelligence/quality` endpoint compared latest prices/predictions/consensus/sentiment timestamps against a 36-hour calendar threshold. Since EGX is closed Fri–Sat, every weekend legitimately-fresh data looked "41.6h stale" with a yellow warning pill, signalling a false pipeline failure to investors.

**Fix:** `marketAdjustedAgeHours()` in [web-ui/server.js](web-ui/server.js) subtracts Fri (UTC day 5) and Sat (UTC day 6) hours from the age calculation. Sources that only update on trading days are flagged `marketAware: true` in the quality endpoint. Calendar age is still exposed as `calendar_age_hours` for debugging.

### 18.3 Sample-reliability flag on track-record cards

**Problem:** Because quality gates + cost gate activated Mar 21 + Apr 3, the 30-day window contains ~10 evaluated trades — too few for Sharpe / max-drawdown / profit-factor to be statistically meaningful. The dashboard displayed Sharpe -8.88, DD 89.44 %, Win 26.1 % as if they were stable figures.

**Fix:** [`kpiForWindow`](web-ui/routes/track-record.js) now returns a `sample_reliability` field:
- `≥30 trades` → `high` (no badge)
- `10–29 trades` → `preliminary` (amber badge)
- `<10 trades`  → `insufficient` (red badge)

The frontend renders the badge on each rolling card so investors can distinguish transient post-gate metrics from long-run performance.

---

*EGX branch (`main`). For Saudi/Tadawul version see `docs/brd-ksa.md` on the `xmore-ksa` branch.*
