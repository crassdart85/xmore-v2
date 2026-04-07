# Business Requirements Document — Xmore KSA (Tadawul)
**Version:** 1.2 | **Date:** April 2026 | **Status:** Active

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
- Approximate trading days/year: ~250 (Sun–Thu, excluding Saudi national holidays)

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
| `engines/evaluate_performance.py` | `TASI_SYMBOLS = ['TASI.INDX', '^TASI', '2222.SR']` on KSA branch |
| `engines/timemachine_data.py` + `timemachine_engine.py` | 41 .SR symbols, `^TASI` key, `TASI_BASE=12000` |
| `engines/agent_weights.py` | Softmax dynamic agent weights (T=2.0, floor 5%) + audit log |
| `engines/event_detector.py` | News event detection (SAMA, CMA, TASI rebalance) → targeted sentiment refresh |
| `engines/job_locks.py` | Advisory TTL-based pipeline locking |
| `engines/macro_data.py` | MacroDataProvider: SAMA rate, USD/SAR, CPI, GDP → composite risk score |
| `web-ui/services/openbbMcpBridge.js` | MCP bridge: live quotes (SAR) + macro context for RAG chat |
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

### 8.4 Dynamic Agent Weighting (April 2026)

`engines/agent_weights.py` replaces static equal weights with softmax-based dynamic weights computed from recent 30-day directional accuracy. Temperature=2.0, floor=5%. Weight history logged to `agent_weights_log` table.

### 8.5 Regime Feedback into Agents (April 2026)

`engines/regime_model.py` `get_current_regime()` returns bull/bear/high_vol labels. `REGIME_SIGNAL_MODIFIERS` in `run_agents.py` applies per-regime bias adjustments and threshold gates before consensus.

### 8.6 Event-Triggered Sentiment Refresh (April 2026)

`engines/event_detector.py` (`EventDetector`) scans recent news before the agent pipeline runs. Detects:
- SAMA rate decisions (affects all stocks)
- Earnings announcements (affects mentioned symbols)
- CMA regulatory actions (suspensions, delistings)
- TASI/MT30 index rebalances
- Opening price gaps >3%

Triggers targeted `collect_sentiment()` for affected symbols.

### 8.7 Calibrated Evaluation Metrics (April 2026)

`evaluate.py` now computes multi-metric scoring: magnitude score, Brier calibration, signal strength, and actual return. `evaluate_performance.py` computes IC via Spearman rank correlation. Exposed via `/api/track-record/summary`.

### 8.8 OpenBB MCP Bridge (April 2026)

`web-ui/services/openbbMcpBridge.js` enriches the RAG chat with live Tadawul quotes (SAR) and KSA macro context (SAMA rate, USD/SAR). "Live data" badge (EN/AR) on enriched responses.

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

Runs on `xmore-ksa` branch. Same schedule as Tadawul branch adapted for Tadawul market hours (open ~06:00 UTC, close ~10:00 UTC):

| Job | Cron | Notes |
|-----|------|-------|
| `intraday-price-update` | `0 7,8,9,10,11,12 * * 0-4` | Prices only — no schema init |
| `intraday-news-update` | `0 7,9,11 * * 0-4` | |
| `post-market-pipeline` | `30 12 * * 0-4` | 90m timeout |
| `daily-pipeline` | `0 22 * * 0-5` | 60m timeout |
| `catchup-evaluation` | `0 6,18 * * *` + `15 12 * * *` | 30m timeout; 12:15 staggers past price-update |
| `etf-ksa-all` | `30 13 * * 0-4` | KSA ETFs |
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
| Pro | Advanced analytics; TASI proxy chart (`tasiChartWidget` — native Chart.js, 2222.SR 60-day), Tadawul leaders price table (`ksaIndicesWidget` — native from `/api/prices`); section class `pro-ksa-section` |
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
- **Ticker tape:** Uses TradingView ticker-tape widget (shows `—` for unsupported TADAWUL symbols but no blocking popup)
- **TASI chart (`tasiChartWidget`):** Native Chart.js area chart showing Saudi Aramco (2222.SR) 60-day close from `/api/prices/history/:symbol` — replaces broken TradingView advanced-chart widget (TADAWUL exchange not on free tier → popup blocker)
- **Tadawul leaders (`ksaIndicesWidget`):** Native HTML table from `/api/prices` — replaces broken TradingView market-overview widget
- **CSS ticker classes:** `.ksa-ticker-tape/.ksa-ticker-inner/.ksa-ticker-item`; items separated by `·` sentinel
- **Company names:** `getCompanyName()` strips `.SR` suffix for display fallback
- **Alert placeholder:** `2222.SR` (Saudi Aramco)
- **Intelligence Pulse:** collapsible; state persists via `localStorage` key `intelligencePulseCollapsed`

### 12.5 AI Assistant Widget

`web-ui/public/assistant-widget.js/css` — assistant aliases include: `usd sar fx dollar gold 24k 21k currency macro rates foreign exchange دولار ريال ذهب 24 21`

---

## 13. Seeded Stock Universe

41 `.SR` stocks seeded in `egx30_stocks` table (legacy table name retained for schema compatibility — holds KSA/Tadawul data).

Representative examples: `2222.SR` (Aramco), `1120.SR`, `1180.SR`, `2010.SR`, `2020.SR`, `2030.SR`, `2050.SR`, `2060.SR`, `2080.SR`, `2090.SR`, `2100.SR`, `2110.SR`, `2120.SR`, `2130.SR`, `2140.SR`, `2160.SR`, `2170.SR`, `2180.SR`, `2190.SR`, `2200.SR`, `2210.SR`, `2220.SR`, `2230.SR`, `2240.SR`, `2250.SR`, `2260.SR`, `2270.SR`, `2280.SR`, `2290.SR`, `2300.SR`, `2310.SR`, `2320.SR`, `2330.SR`, `2340.SR`, `2350.SR`, `4001.SR`, `4002.SR`, `4003.SR`, `4004.SR`, `4005.SR`, `4006.SR`

All server.js queries filter `WHERE symbol LIKE '%.SR'` (predictions, evaluations, consensus, sentiment, performance, changes, prices).

---

## 14. KSA Schema Notes

| Item | Detail |
|------|--------|
| `prices` table | NO `market_id` column — filter by `symbol LIKE '%.SR'`, never `market_id = 'KSA'` |
| `/api/prices/history/:symbol` | Added Apr 6 2026 — returns last N days OHLCV for one symbol; `?days=` param (default 60, max 365); used by native TASI proxy chart in pro.js |
| `consensus_results` date column | `prediction_date` (not `timestamp`, not `date`) — `ksa-signals.js` aliases as `prediction_date AS timestamp` |
| `regime_flag` | Does NOT exist in `consensus_results` — never SELECT it |
| KSA-only columns on `trade_recommendations` | `signal_type`, `xmore_score`, `notes` — added via ALTER TABLE in `init-db-ksa.js` |
| `run_agents_ksa.py` | Writes `signal_type` (not legacy `signal` column) |
| TASI benchmark | Stored as symbol `TASI.INDX`; fallback to `^TASI` / `2222.SR` proxy |
| `agent_weights_log` | Softmax weight audit trail (added April 2026 via `init-db-ksa.js`) |
| `macro_indicators` | SAMA rate, USD/SAR, CPI, GDP cached by MacroDataProvider |
| `job_locks` | Advisory pipeline locking (TTL-based) |
| `evaluations` new columns | `magnitude_score`, `calibration_score`, `signal_strength`, `actual_return` |
| `predictions` new column | `confidence_score` (consensus confidence from softmax weights) |

---

## 15. Security & Operations

### 15.1 Environment Secrets (GitHub + Render)

**Render (`xmore-ksa` service):** `DATABASE_URL`, `JWT_SECRET`, `GOOGLE_API_KEY`, `NEWS_API_KEY`, `FINNHUB_API_KEY`, `EODHD_API_KEY`, `MARKETAUX_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`

**GitHub Actions (repo secrets):** `KSA_DATABASE_URL` ← **must be the External Database URL from `ksa-trading-db` on Render** (not the internal hostname). `ksa-branch-scheduled.yml` sets `DATABASE_URL: ${{ secrets.KSA_DATABASE_URL }}`. Using the shared `DATABASE_URL` (Tadawul DB) caused KSA data to contaminate Tadawul database — fixed Apr 2026.

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
| KSA pipeline writing to Tadawul DB (DB empty) | `ksa-branch-scheduled.yml` was using `secrets.DATABASE_URL` (Tadawul DB). Fixed Apr 2026: now uses `secrets.KSA_DATABASE_URL`. Render internal hostname won't work from GH Actions — use External Database URL. |
| `/pro` TradingView TADAWUL popup | `embed-widget-advanced-chart` + `embed-widget-market-overview` both block with "symbol only available on TradingView" for TADAWUL exchange (not on free plan). Fixed Apr 6 2026: replaced with native Chart.js + `/api/prices` table. |
| `/pro` stat pills showing `â€"` mojibake | `pro.html` had raw UTF-8 em-dash bytes `\xe2\x80\x94` served without explicit charset. Fixed Apr 6 2026: replaced with `&mdash;` HTML entities. `pro.js` had full cp1252-in-UTF-8 double-encoding affecting em-dash returns and Arabic i18n strings — fixed by reversing the encoding at byte level. |

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
- [ ] `KSA_DATABASE_URL` repo secret set to **External** Database URL from `ksa-trading-db` (Render → PostgreSQL → Connection → External Database URL)
- [ ] `DATABASE_URL` repo secret remains set to Tadawul DB (used by main branch workflows only)
- [ ] `intraday-price-update` job has NO schema init step
- [ ] All other schema init steps have `timeout-minutes: 2` + `continue-on-error: true`
- [ ] Verify 41 `.SR` stocks seeded in `egx30_stocks` table (legacy name; holds KSA rows)

---

## 19. Signal Quality & Presentation Fixes (April 5, 2026)

Three production issues surfaced after the April 3–4 quality-gate rollout produced a 10-day evaluation sample with misleading headline metrics.

### 19.1 Horizon-scaled Tier 2 cost gate

**Problem:** The cost gate in `run_agents_ksa.py` compared a **1-day ATR%** to a **5-day hold cost+profit threshold** (1.9 %). Because the typical Tadawul large-cap daily ATR is 0.8–1.5 %, every directional signal was forced to HOLD, producing a dashboard of all-HOLD with 0.00 % expected edge.

**Fix:** Scale 1-day ATR% by √5 to approximate the 5-day expected move, then compare against the threshold:

```
5d_expected_move = ATR_1d × √5
gate: 5d_expected_move < (round_trip_cost 0.4 % + min_net_profit 1.0 %) = 1.4 % → HOLD
```

- 2222.SR (ATR ~1.1 %): 5d move 2.46 % → **PASS**
- 1180.SR (ATR ~1.3 %): 5d move 2.91 % → **PASS**
- Previously all such symbols were killed.

### 19.2 Market-aware data-freshness warnings

**Problem:** On Fri/Sat the `/api/intelligence/quality` endpoint compared latest prices/predictions/consensus/sentiment timestamps against a 36-hour calendar threshold. Since Tadawul is closed Fri–Sat, every weekend legitimately-fresh data looked stale with a yellow warning pill, signalling a false pipeline failure to investors.

**Fix:** `marketAdjustedAgeHours()` in `web-ui/server.js` subtracts Fri (UTC day 5) and Sat (UTC day 6) hours from the age calculation. Sources that only update on trading days are flagged `marketAware: true` in the quality endpoint. Calendar age is still exposed as `calendar_age_hours` for debugging.

### 19.3 Sample-reliability flag on track-record cards

**Problem:** Because quality gates + cost gate activated Mar 21 + Apr 3, the 30-day window contains ~10 evaluated trades — too few for Sharpe / max-drawdown / profit-factor to be statistically meaningful. The dashboard displayed misleading headline figures.

**Fix:** `kpiForWindow` in `web-ui/routes/track-record.js` now returns a `sample_reliability` field:
- `≥30 trades` → `high` (no badge)
- `10–29 trades` → `preliminary` (amber badge)
- `<10 trades`  → `insufficient` (red badge)

The frontend renders the badge on each rolling card so investors can distinguish transient post-gate metrics from long-run performance.

---

*KSA branch (`xmore-ksa`). For Saudi Exchange version see `docs/brd-eg.md` on the `main` branch.*
