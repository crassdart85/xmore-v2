# Business Requirements Document — Xmore KSA (Tadawul)
**Version:** 1.0 | **Date:** March 2026 | **Status:** Active

---

## 1. Executive Summary

Xmore KSA is the Saudi/Tadawul adaptation of the Xmore AI trading assistant. It delivers daily multi-agent predictions, walk-forward backtested strategies, and a real-time web dashboard for Saudi Exchange (Tadawul)-listed equities, denominated in Saudi Riyal (SAR).

**Live deployment:** https://xmore-ksa.onrender.com

---

## 2. Problem Statement

Saudi retail investors lack affordable, systematic tools for Tadawul equity analysis. Professional-grade signal generation, backtesting, and position sizing are inaccessible or cost-prohibitive. Xmore KSA fills this gap with an automated pipeline that runs daily on GitHub Actions and surfaces results through a mobile-friendly web UI.

---

## 3. Target Market

- Saudi and Gulf retail and semi-professional equity traders
- Tadawul-listed stocks (.SR suffix; e.g. `2222.SR` for Saudi Aramco)
- Primary index benchmark: TASI (Tadawul All Share Index)
- Currency: Saudi Riyal (SAR)
- Timezone: Riyadh (UTC+3)
- Approximate trading days/year: ~249–252

---

## 4. Core Objectives

| # | Objective |
|---|-----------|
| 1 | Generate daily buy/sell/hold signals for Tadawul equities using a 6-agent AI pipeline |
| 2 | Provide walk-forward backtested performance metrics with friction costs |
| 3 | Size positions using Kelly Criterion with shrinkage and adaptive weighting |
| 4 | Surface signals, portfolio, and analytics in SAR through a responsive web dashboard |
| 5 | Run fully automated on GitHub Actions with zero manual intervention |

---

## 5. Business Model

- Free-tier hosted on Render.com (web service + PostgreSQL)
- GitHub Actions free tier for automation
- No subscription or monetisation currently; internal research tool

---

## 6. Data Sources

| Source | Usage |
|--------|-------|
| EODHD | Primary EOD price data for .SR symbols |
| News APIs (NewsAPI, Marketaux) | Sentiment & headline extraction |
| Finnhub | Supplementary fundamentals |
| Google Gemini (gemini-2.5-flash) | AI agent reasoning |
| EODHD | ETF price data |
| `engines/fetch_tasi_benchmark.py` | TASI daily index prices (stored as `TASI.INDX`) |

---

## 7. System Architecture

### 7.1 Infrastructure

| Component | Platform | Details |
|-----------|----------|---------|
| Web dashboard | Render.com web service | Node.js / Express |
| Database | Render.com PostgreSQL | `ksa-trading-db` |
| Automation | GitHub Actions | `crassdart85/xmore-v2` (`xmore-ksa` branch) |
| Schema init | `web-ui/init-db-ksa.js` | Runs in `buildCommand` |

### 7.2 Key Source Files

| File | Role |
|------|------|
| `web-ui/server.js` | Express API server (all queries filter `WHERE symbol LIKE '%.SR'`) |
| `web-ui/init-db-ksa.js` | PostgreSQL schema + seed for KSA (`safeDDL` pattern) |
| `web-ui/routes/trades.js` | Trade recs, portfolio (SAR fields: `cost_sar`, `value_sar`, `pnl_sar`) |
| `web-ui/routes/ksa-signals.js` | `/api/ksa/signals/*`, `/api/ksa/execution/:ticker`, `/api/ksa/context/:ticker`, `/api/ksa/regime`, `/api/ksa/performance/summary` |
| `web-ui/routes/screening.js` | Screening engine API |
| `web-ui/routes/rag.js` | RAG semantic search |
| `web-ui/routes/etf.js` | ETF analytics |
| `web-ui/public/app.js` | Frontend (~4000+ lines); COMPANY_NAMES and SECTOR_MAP use .SR stocks |
| `web-ui/public/portfolioForecasts.js` | Forecast Portfolios tab |
| `web-ui/public/briefing.js` | Daily briefing; action card prices show "SAR ${price}" |
| `web-ui/public/trades.js` | Portfolio table: Cost (SAR) / Value (SAR) / P&L (SAR) |
| `web-ui/public/timemachine.js` | Time Machine; all amounts in SAR; `.SR` suffix handling |
| `engines/screening_engine.py` | Stock screening backend |
| `engines/signal_enrichment.py` | Signal enrichment pipeline |
| `engines/kelly_allocator.py` | Kelly position sizing |
| `engines/portfolio_rebalancer.py` | Portfolio rebalancing |
| `engines/backtest_friction.py` | Friction-aware backtest (Tadawul fee structure) |
| `engines/pivot_engine.py` | Pivot levels, ATR, candlestick patterns |
| `engines/backtest.py` | Walk-forward backtest |
| `engines/fetch_tasi_benchmark.py` | TASI daily prices; 3-strategy: EODHD → proxy; stores as `TASI.INDX` |
| `engines/evaluate_performance.py` | `EGX30_SYMBOLS = ['TASI.INDX', '^TASI', '2222.SR']` on KSA branch |
| `engines/timemachine_data.py` + `timemachine_engine.py` | 41 .SR symbols, `^TASI` key, `TASI_BASE=12000` |
| `backfill_history.py` | Bulk historical price backfill |
| `render-ksa.yaml` | Render deployment config for KSA |

---

## 8. AI Pipeline

### 8.1 Six-Agent Architecture

Each trading day the pipeline runs six specialised agents in sequence:

| Agent | Role |
|-------|------|
| Fundamentals | P/E, EPS, revenue trends |
| Technical | RSI, MACD, Bollinger, pivot levels |
| Sentiment | News headlines scoring |
| Macro | USD/SAR rate, SAMA rate (~6.0%), sector flows |
| Risk | Volatility, ATR, stop-loss calibration |
| Orchestrator | Synthesises all agent outputs → final signal |

### 8.2 Signal Output

- **Signal types:** BUY / SELL / HOLD (stored in `signal_type` column on `trade_recommendations`)
- **Xmore Score:** 0–100 composite conviction score (stored in `xmore_score` column)
- **Conviction gate:** LOW conviction BUY (score < 40) is discarded before storage
- **Consensus:** multi-day rolling consensus; `consensus_results.prediction_date` column (not `timestamp`, not `date`)

### 8.3 Market Regime Detection

`_detect_market_regime()` uses MA/volatility analysis. Result written to `regime_log` after each detection run. **`regime_flag` column does NOT exist in `consensus_results`** — never SELECT it.

---

## 9. Position Sizing — Kelly Criterion

`engines/kelly_allocator.py`:

- Full Kelly fraction computed from win rate + average win/loss ratio
- **Adaptive weighting:** blends 30d / 90d win rate with alpha, sample-size shrinkage, and drift penalties
- Half-Kelly applied as default for risk management
- Output fed directly into live pipeline via `run_agents_ksa.py`

Note: `run_agents_ksa.py` writes `signal_type` (not the legacy `signal` column).

---

## 10. Transaction Costs (Tadawul)

Friction model in `engines/backtest_friction.py` uses Tadawul fee structure:

| Cost Component | Rate |
|---------------|------|
| Brokerage commission | ~0.15–0.25% per side (broker-dependent) |
| CMA levy | 0.0033% |
| Tadawul fee | 0.0046% |
| VAT on fees | 15% |
| Effective round-trip | ~0.35–0.55% total |

**Performance reporting is net-of-transaction-cost throughout.**

---

## 11. GitHub Actions Schedule (UTC)

Runs on `xmore-ksa` branch. Same schedule as EGX branch adapted for Tadawul market hours (open ~06:00 UTC, close ~10:00 UTC):

| Job | Cron | Notes |
|-----|------|-------|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | Prices only — no schema init |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | |
| `post-market-pipeline` | `30 12 * * 0-4` | 90m timeout |
| `daily-pipeline` | `0 22 * * 0-5` | 60m timeout |
| `catchup-evaluation` | `0 6,12,18 * * *` | 30m timeout |
| `etf-egx-all` | `30 13 * * 0-4` | KSA ETFs |
| `etf-global-prices` | `30 21 * * 1-5` | |
| `etf-rag-embedding` | `15 6,10,14,20 * * *` | 4×/day |
| `weekly-backtest` | `0 7 * * 0` | |

All schema init steps: `timeout-minutes: 2` + `continue-on-error: true`.

---

## 12. Web Dashboard Features

### 12.1 Navigation Structure

| Section | Description |
|---------|-------------|
| Home / Briefing | Daily market briefing; action card prices in SAR |
| Signals (KSA) | Full signal table with filters, conviction scores for .SR stocks |
| Watchlist / Consensus | Multi-day consensus view per Tadawul ticker |
| Portfolio | Position tracker with SAR P&L, Kelly-sized allocations |
| Track Record | Live performance vs TASI benchmark |
| Screening | Multi-factor stock screener |
| Forecast Portfolios | AI-projected portfolio outcomes |
| ETF | KSA and global ETF analytics (`_etfClassify` detects KSA/TADAWUL/SAR) |
| Rates | USD/SAR FX rate + Gold SAR/gram (24K + 21K) history charts |
| Session Sheet | Intraday session-level trade log |
| Pro | Advanced analytics, TASI chart widget (`tasiChartWidget`), Tadawul overview (`ksaIndicesWidget`); section class `pro-ksa-section` |
| RAG / Docs | Semantic search over knowledge base |
| Time Machine | Hypothetical historical portfolio simulator; all amounts in SAR |

### 12.2 Currency & Rates

- **All currency:** SAR (Saudi Riyal)
- **FX rates API (`/api/fx-rates`):** returns `{USD_SAR, GOLD_24K_SAR_G, GOLD_21K_SAR_G, updated}`
- **Gold computation:** `GOLD_24K_SAR_G = (xau_usd / 31.1035) * usd_sar`; 21K = 24K × (21/24)
- **FX history:** `usd_sar`, `xau_usd` stored; 24K/21K SAR computed on-the-fly
- **Rates tab sparklines:** USD/SAR rate + Gold 24K (SAR/g) + Gold 21K (SAR/g)

### 12.3 Portfolio Fields (SAR)

| API field | UI label |
|-----------|----------|
| `cost_sar` | Invested (SAR) |
| `value_sar` | Market Value (SAR) |
| `pnl_sar` | P&L (SAR) |
| `total_cost_sar` | Total Invested (SAR) |
| `total_value_sar` | Total Value (SAR) |
| `total_pnl_sar` | Total P&L (SAR) |

`renderPortfolioTotals` uses locale `en-SA` and appends 'SAR'.

### 12.4 UI Conventions

- **Header:** All pages use `<header class="x-topbar x-topbar--dark">` with unified nav links
- **Mobile:** hamburger pattern `id="<Page>MobileMenuBtn"` / `id="<Page>MobileMenuDropdown"`
- **Language:** EN + AR (Arabic RTL supported throughout); translation keys use SAR labels
- **Ticker tape:** Uses native `/api/prices` ticker (TradingView free plan doesn't support TADAWUL); CSS classes `.ksa-ticker-tape/.ksa-ticker-inner/.ksa-ticker-item`; items separated by `·` sentinel
- **Company names:** `getCompanyName()` strips `.SR` suffix for display fallback
- **Alert placeholder:** `2222.SR` (Saudi Aramco)
- **Intelligence Pulse:** collapsible; state persists via `localStorage` key `intelligencePulseCollapsed`

### 12.5 AI Assistant Widget

`web-ui/public/assistant-widget.js/css` — assistant aliases include: `usd sar fx dollar gold 24k 21k currency macro rates foreign exchange دولار ريال ذهب 24 21`

---

## 13. Seeded Stock Universe

41 `.SR` stocks seeded in `egx30_stocks` table (fixed March 2026 — was incorrectly seeding 190 EGX `.CA` stocks).

Representative examples: `2222.SR` (Aramco), `1120.SR`, `1180.SR`, `2010.SR`, `2020.SR`, `2030.SR`, `2050.SR`, `2060.SR`, `2080.SR`, `2090.SR`, `2100.SR`, `2110.SR`, `2120.SR`, `2130.SR`, `2140.SR`, `2160.SR`, `2170.SR`, `2180.SR`, `2190.SR`, `2200.SR`, `2210.SR`, `2220.SR`, `2230.SR`, `2240.SR`, `2250.SR`, `2260.SR`, `2270.SR`, `2280.SR`, `2290.SR`, `2300.SR`, `2310.SR`, `2320.SR`, `2330.SR`, `2340.SR`, `2350.SR`, `4001.SR`, `4002.SR`, `4003.SR`, `4004.SR`, `4005.SR`, `4006.SR`

All server.js queries filter `WHERE symbol LIKE '%.SR'` (predictions, evaluations, consensus, sentiment, performance, changes, prices).

---

## 14. KSA Schema Notes

| Item | Detail |
|------|--------|
| `prices` table | NO `market_id` column — filter by `symbol LIKE '%.SR'`, never `market_id = 'KSA'` |
| `consensus_results` date column | `prediction_date` (not `timestamp`, not `date`) — `ksa-signals.js` aliases as `prediction_date AS timestamp` |
| `regime_flag` | Does NOT exist in `consensus_results` — never SELECT it |
| KSA-only columns on `trade_recommendations` | `signal_type`, `xmore_score`, `notes` — added via ALTER TABLE in `init-db-ksa.js` |
| `run_agents_ksa.py` | Writes `signal_type` (not legacy `signal` column) |
| TASI benchmark | Stored as symbol `TASI.INDX`; fallback to `^TASI` / `2222.SR` proxy |

---

## 15. Security & Operations

### 15.1 Environment Secrets (GitHub + Render)

`DATABASE_URL`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `GOOGLE_API_KEY`, `JWT_SECRET`, `EODHD_API_KEY`, `MARKETAUX_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`

### 15.2 Auth Pattern

`authMiddleware` sets `req.userId` (not `req.user.userId`). JWT-based session auth.

### 15.3 Claude Code Hooks (Local Dev — March 2026)

Configured in `.claude/settings.json` + `.claude/hooks/` (local-only, gitignored):

| Hook | Event | Purpose |
|------|-------|---------|
| `check-syntax.js` | PostToolUse (Edit/Write) | Runs `node --check` / `python -m py_compile` after every file edit. Catches `??`→`?` corruption. Exit 1 = surfaces error. |
| `guard-bash.js` | PreToolUse (Bash) | Blocks: force-push to main/master, `git reset --hard` to non-HEAD, bypassing git hooks. Exit 2 = blocks. |
| `pre-compact.js` | PreCompact | Logs pre-compaction summary to `.claude/compact-log.txt` (async). |

---

## 16. Known Issues & Constraints

| Issue | Mitigation |
|-------|-----------|
| `??`/`\|\|`→`?` JS corruption (full-page blank) | `node --check` via PostToolUse hook; `portfolioForecasts.js` fixed Mar 2026 |
| `pd.read_sql()` deadlock with psycopg2 | Use `cursor.execute()` + `fetchall()` + `pd.DataFrame` pattern |
| `CREATE INDEX` deadlock in `database.py` | Use `_safe_create_index(cursor, sql)` |
| Render "No open ports detected" | `init-db-ksa.js` must be in `buildCommand`, not `startCommand` |
| Gemini 404 on deprecated models | Use `gemini-2.5-flash` + `text-embedding-005` |
| `authMiddleware` 500 errors | Always use `req.userId`, never `req.user.userId` |
| KSA `/execution/:ticker` HTTP 500 | Check `signal_type`/`xmore_score` columns exist; prices query must NOT filter `market_id` |
| KSA signals HTTP 500 | `consensus_results` column is `prediction_date`; never SELECT `regime_flag` |
| `consensus_results` stale .CA rows | server.js `WHERE symbol LIKE '%.SR'` filter removes them; will clear when KSA pipeline runs |

---

## 17. Database Patterns

### 17.1 DDL (init-db-ksa.js)

All DDL uses `safeDDL(db, sql, timeoutMs)` transaction wrapper with `SET LOCAL lock_timeout='5s'`:
- Indexes: `safeCreateIndex(db, sql)` — 120s timeout
- Columns: `safeAddColumn(db, sql)` — 10s timeout
- Global session: `lock_timeout=5s`, `statement_timeout=0`
- Disable `statement_timeout` before large seed INSERTs

### 17.2 Server.js DB Wrapper

Use `.all()` / `.get()` / `.run()` only — never `.query()`.

### 17.3 News Aggregator INSERTs

Each INSERT in `news_aggregator.py` must use `SAVEPOINT intel_insert` / `ROLLBACK TO SAVEPOINT`.

---

## 18. Deployment Checklist

- [ ] `render-ksa.yaml` `buildCommand: cd web-ui && npm install && node init-db-ksa.js`
- [ ] `render-ksa.yaml` `startCommand: node web-ui/server.js`
- [ ] Same settings updated in Render dashboard (buildCommand field)
- [ ] All secrets configured in Render dashboard for `xmore-ksa` service
- [ ] GitHub Actions secrets match Render env vars
- [ ] `intraday-price-update` job has NO schema init step
- [ ] All other schema init steps have `timeout-minutes: 2` + `continue-on-error: true`
- [ ] Verify 41 `.SR` stocks seeded in `egx30_stocks` table (not `.CA` stocks)

---

*KSA branch (`xmore-ksa`). For Egyptian Exchange version see `docs/brd-eg.md` on the `main` branch.*
