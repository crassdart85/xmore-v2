# Business Requirements Document — Xmore (EGX)
**Version:** 1.5 | **Date:** March 2026 | **Status:** Active

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
| `catchup-evaluation` | `0 6,12,18 * * *` | 30m timeout |
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

*EGX branch (`main`). For Saudi/Tadawul version see `docs/brd-ksa.md` on the `xmore-ksa` branch.*
