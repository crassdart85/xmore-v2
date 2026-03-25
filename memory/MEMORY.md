# Xmore Project Memory

## Project Structure
- **Python backend**: data collection, ML agents, predictions (root level)
- **Node.js web UI**: `web-ui/` â€” Express server, API, dashboard
- **Database**: SQLite (local dev), PostgreSQL (production on Render)
- **Frontend**: Vanilla JS, CSS â€” bilingual EN/AR dashboard

## Mar 25, 2026 - Workflow Branch Alignment
- Main-branch workflow files no longer hard-code `ref: main` in `actions/checkout`.
- `scheduled-tasks.yml`, `backfill-predictions.yml`, and `run-backtest.yml` now use `${{ github.ref_name }}` so manual/branch runs use the branch that triggered them.
- Added `.github/workflows/ksa-branch-scheduled.yml` on `main`:
  - required because GitHub scheduled workflows only run from the default branch
  - each job explicitly checks out `xmore-ksa`
  - this is now the source of truth for scheduled KSA automation while `main` remains default
- Takeaway: branch-aware checkout and default-branch dispatching are both required for multi-branch automation in this repo.

## Key File Paths
- `web-ui/server.js` â€” Express app, all API endpoints
- `web-ui/init-db.js` â€” PostgreSQL table creation + full EGX stock seed (~190)
- `web-ui/middleware/auth.js` â€” JWT auth middleware
- `web-ui/routes/auth.js` â€” signup/login/logout/me
- `web-ui/routes/stocks.js` â€” GET /api/stocks
- `web-ui/routes/watchlist.js` â€” watchlist CRUD
- `web-ui/routes/trades.js` â€” trade recommendations + history
- `web-ui/routes/briefing.js` â€” daily briefing API (GET /api/briefing/today)
- `web-ui/public/app.js` â€” main dashboard logic (~1900+ lines)
- `web-ui/public/auth.js` â€” frontend auth module
- `web-ui/public/watchlist.js` â€” frontend watchlist module
- `web-ui/public/trades.js` â€” frontend trades/portfolio module
- `web-ui/public/briefing.js` â€” frontend briefing module (7-section dashboard)
- `web-ui/public/performance-dashboard.js` â€” performance metrics + equity curve
- `web-ui/public/style.css` â€” main CSS with CSS vars, responsive, RTL (~3050 lines)
- `web-ui/public/performance-dashboard.css` â€” performance tab styles
- `web-ui/public/auth.css` â€” auth modal + watchlist card styles
- `engines/briefing_generator.py` â€” pure computation: market pulse, sectors, risk, sentiment
- `engines/garch_engine.py` â€” GARCH/GJR-GARCH/EGARCH fitting + multivariate path simulation (Phase 1)
- `engines/regime_model.py` â€” Gaussian HMM regime detection + Markov path simulation (Phase 2)
- `engines/simulation_core.py` â€” unified SimulationEngine with SimulationConfig; backward-compatible simulate_paths()
- `engines/diagnostics.py` â€” GARCH + HMM + simulation output diagnostics (statistical tests + matplotlib plots)

## Architecture Notes
- DB abstraction: unified `.all()/.get()/.run()` wrapper for both PG and SQLite
- Route modules use `attachDb(db, isPostgres)` pattern
- Placeholder helper: `ph(n)` returns `$n` (PG) or `?` (SQLite)
- Translations split across 6 modules: app.js (`TRANSLATIONS`, `t()`), auth.js (`authText`, `at()`), watchlist.js (`wlText`, `wt()`), trades.js (`tradesText`, `tt()`), briefing.js (`briefingText`, `bt()`), performance-dashboard.js (`PERF_TRANSLATIONS`, `pt()`)
- JWT auto-refresh: tokens refreshed when <3 days remaining
- `escapeHtml()` defined ONCE in app.js (global scope), used by all modules
- Tab navigation uses `switchToTab()` with URL hash routing (`history.pushState`/`popstate`)

## Completed Features
- Auth system (email/password, bcrypt 12 rounds, JWT httpOnly cookies, rate limiting)
- Full EGX stock reference table (~190 stocks across 15 sectors, bilingual names)
- User watchlist (search, add/remove, no stock limit) â€” tab always visible, login prompt on click
- **Watchlist-only filtering**: logged-in users see ONLY their followed stocks across all tabs
- Trade recommendations + portfolio tracking
- 3-layer consensus pipeline display
- **Daily Market Briefing**: 7 sections (market pulse, actions today, portfolio snapshot, watchlist heatmap, sector breakdown, risk alerts, sentiment snapshot)
- **Performance Dashboard**: proof of edge, stability metrics, agent accountability, transparency/audit, equity curve chart

## UI/UX Audit & Fixes (Feb 2026)
- **Footer**: moved outside Portfolio tab to be globally visible
- **A11Y**: ARIA roles (dialog, tablist/tab/tabpanel), `:focus-visible` outlines, `prefers-reduced-motion`, color-blind arrows
- **Security**: global `escapeHtml()`, `textContent` for error output (no XSS via innerHTML)
- **I18N**: all perf-dashboard strings translated (26 keys EN+AR), briefing action badges, page title translated
- **Dark mode**: `--text-muted` bumped from `#71717a` to `#9ca3af` for contrast
- **Mobile tabs**: horizontal scroll (`overflow-x: auto`, hidden scrollbar) instead of wrapping
- **URL routing**: tabs use hash routing (`#predictions`, `#briefing`, etc.) with back/forward support
- **RTL fixes**: action-card borders flipped, sector-row reversed, result-card borders
- **Code quality**: deduplicated `escapeHtml()`, `.retry-btn` CSS class, `.perf-action-btn` CSS added

## Frontend UX Upgrade Sprint (Feb 15, 2026)
- CountUp.js animated counters, Notyf toasts, Lightweight Charts equity curve, shimmer skeletons (7 types), micro-interactions, empty states, full keyboard A11Y
- CDN: CountUp.js 2.8.0, Notyf 3.x, Lightweight Charts 4.1.1 â€” all with `typeof X !== 'undefined'` graceful fallback
- Global utils in app.js: `escapeHtml()`, `animateValue()`, `showToast()`, `showSkeleton()`, `clearSkeleton()`, `renderEmptyState()`

## Track Record UX Refresh (Mar 16, 2026)
- web-ui/public/track-record.css: mobile cleanup at <=640px, responsive header controls, feed wrapping, sector rows stacked, tracker panel becomes bottom sheet
- web-ui/public/track-record.html: agent + top-stocks tables flagged for mobile card layout
- web-ui/public/track-record.js: localized data-labels for mobile cards (including log table) and language toggle refresh

## UI/UX Unification & Mobile Readability (Mar 16, 2026)
- Shared UI token layer + topbar (`web-ui/public/base.css`) applied across public pages.
- Language persistence unified on `localStorage('lang')` for Track Record, Pro, Session.
- Public HTML/JS normalized to UTF-8 to fix encoding artifacts.
- Consistent nav links across pages; added Session link in main dashboard header.
- Mobile card layouts for dense tables (dashboard tabs, track record, session, comparisons, ETF tables).
- Localized labels for comparison/multi-horizon and ETF cards/tables.
- Base font sizes standardized to 14px on major dashboards; reduced all-caps labels.
- Reduced-motion preferences handled globally.

## Track Record Copy Tweak (Mar 16, 2026)
- `web-ui/public/track-record.html`: header badge shortened to ?Live pre-market signals?.

## CI/CD Pipeline (current â€” 7 jobs)
- **`intraday-price-update`**: `'0 7,8,9,10,11,12 * * 0-4'` (Sunâ€“Thu, EGX hours) â€” `collect_data.py --prices-only`
- **`intraday-news-update`**: `'0 7,9,11 * * 0-4'` (3Ã— trading day) â€” news + RSS + news RAG ingestion
- **`post-market-pipeline`**: `'30 12 * * 0-4'` â€” prices â†’ news â†’ sentiment â†’ agents â†’ evaluate (no continue-on-error!)
- **`egx-daily-snapshot`**: `'0 14 * * 0-4'` â€” backup EGX data export
- **`daily-pipeline`**: `'0 22 * * 0-5'` (Sunâ€“Fri) â€” full: collect â†’ agents â†’ portfolios â†’ evaluate; depends on post-market-pipeline but runs anyway (`if: always()`)
- **`catchup-evaluation`**: `'0 6,12,18 * * *'` (3Ã— daily) â€” `evaluate.py` + `evaluate_performance.py`
- **`weekly-backtest`**: `'0 7 * * 0'` (Sunday 07:00 UTC = 09:00 Cairo) â€” `run_backtest.py` walk-forward validation
- **Key Python files**: `collect_data.py`, `sentiment_gemini.py`, `run_agents.py`, `evaluate.py`, `engines/evaluate_performance.py`, `engines/generate_portfolios.py`
- **Required secrets**: `DATABASE_URL`, `FINNHUB_API_KEY`, `NEWS_API_KEY`, `GOOGLE_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- **Concurrency**: `cancel-in-progress: false` â€” new runs queue behind running ones; earlier queued runs can be dropped
- **EGX price source**: `data/egx_live_scraper.py` (primary, `http://41.33.162.236/egs4/`) â†’ yfinance fallback (`.CA` suffix)

## ML Agent Improvements (Mar 11, 2026)
- **LightGBM** replaces RandomForestClassifier in `agents/agent_ml.py`; RF fallback if not installed
  - `class_weight='balanced'` handles UP/DOWN minority vs FLAT majority imbalance
  - Two-pass training: WFV (5 folds) â†’ feature selection by gain importance â†’ retrain on all data
  - `_select_top_features()` uses `model.booster_.feature_importance(importance_type='gain')`, keeps top 20 (min 10)
  - Probability calibration removed (LightGBM natively better-calibrated than RF)
  - `lightgbm>=4.3.0` added to `requirements.txt`
- **Walk-forward backtest harness**: `engines/backtest.py`
  - CLI: `python engines/backtest.py --symbol COMI.CA` or `--all`
  - Metrics: accuracy, directional_accuracy, signal_pnl_pct, per-class precision/recall/F1
  - Mirrors `agent_ml._train_model` pipeline exactly (same features, same LightGBM params)
- **Adaptive RSI periods** (`agents/agent_rsi.py`): `_get_vol_regime()` + `_RSI_PERIODS={low:10, normal:14, high:20}`
- **Adaptive MA periods** (`agents/agent_ma.py`): `_get_vol_regime()` + `_MA_PERIODS={low:(8,20), normal:(10,30), high:(15,40)}`
- **Sentiment recency decay** (`sentiment_gemini.py` `collect_sentiment()`): `weight=2^(-days_ago/1.5)`, half-life 1.5 days
- **Vol regime thresholds** (shared): EWMA span=32, daily â€” Low <1.5%, High >3.0%, Normal otherwise
- **GARCH-inspired features** in `features.py`: `garch_ewm_vol`, `vol_of_vol`, `vol_persistence` (no arch lib needed)
- **Macro features**: `brent_return_5d`, `usdegp_return_5d`, `eem_return_5d` â€” stored as MACRO_* in prices table, 5d pct_change
- **USD/EGP source** (`collect_data.py` `_fetch_usdegp_rate()`): CBE official (cbe.org.eg) primary â†’ open.er-api.com â†’ frankfurter.app â†’ exchangerate.host â†’ yfinance fallback. CBE blocked by WAF on cloud IPs; free APIs cover Render. `data_source='cbe_official'` when CBE succeeds.
- **Session Sheet** (`/session`, `web-ui/public/session.html`+`session.css`):
  - Stock table: CODE, Name, Trend (ØµØ§Ø¹Ø¯/Ø¹Ø±Ø¶Ù‰/Ù‡Ø§Ø¨Ø·), Type (Ù…ØªØ§Ø¬Ø±Ø©/Ø§Ø­ØªÙØ§Ø¸), Buy Guide, Stop Loss, Target, Profit%, Risk%, R/R, S2, S1, Pivot, R1, R2
  - Index cards: EGX30/70 pivot levels computed server-side from last 2 OHLC rows
  - API: `GET /api/trades/session-sheet` â†’ `{session_date, stocks[], indices[]}`
  - `engines/pivot_engine.py`: classic floor-trader pivots, ATR(14), EMA10/30 trend, buy guide at S1
  - 10 new columns in `trade_recommendations` (safe-add migration): trend_ar/en, rec_type_ar/en, buy_guide, pivot, r1, r2, s1, s2
  - `get_ohlc_df(symbol, limit=60)` in `run_agents.py`; `enrich_recommendation()` called after risk levels
- **Landing page** (`/landing`, `web-ui/public/landing.html`): pitch, why Xmore, customer, problem, how it works, edge
- **HOLD eval fix** (`evaluate.py`): `abs(pct_change) < 2.0` (was `actual_outcome == "FLAT"` at Â±0.5%)
- **Dynamic agent weights** (`run_agents.py`): accuracy-adjusted via `agent_performance_daily` (PG only)
- **GARCH in risk agent** (`risk_agent.py`): `garch_forecast_vol` preferred over `volatility_20d`
- **High-impact ML improvements** (Mar 2026):
  - **Per-symbol LightGBM models**: `models/{SYMBOL}_predictor.pkl`; in-memory `_model_cache`; global fallback for thin data
  - **Confidence gating**: `CONFIDENCE_THRESHOLD=0.60`; UP/DOWNâ†’HOLD when `max(probs)<0.60`
  - **Optuna HPO**: 25-trial TPE, cached in model file (`best_params` key); skipped on retrains
  - **Regime-gated consensus** (Layer 4 in `consensus_engine.py`): Crisisâ†’UP blocked; Turbulentâ†’conviction downgraded
  - **`_detect_market_regime()`** in `run_agents.py`: tries EGX30.CA â†’ COMI.CA â†’ HRHO.CA as HMM proxy

## Bug Fixes â€” see `memory/bugfixes.md` for full details
- **Feb 2026**: PG `_safe_add_column()`, `INSERT OR IGNORE` â†’ `ON CONFLICT DO NOTHING`, `utils.py` shadowing `utils/` package
- **Mar 2, 2026**: Three fixes pushed â€” see bugfixes.md for details:
  1. `evaluate.py`: `r.ok = 1` â†’ `r.ok = TRUE` (PG BOOLEAN type mismatch, was breaking daily pipeline)
  2. `app.js formatDate()`: now strips ISO timestamp to `YYYY-MM-DD` â€” fixes "02:00" display on date cards
  3. `data/egx_live_scraper.py`: `df.loc[:, ~df.columns.duplicated()]` after rename â€” fixes "truth value of a Series is ambiguous" from duplicate Arabicâ†’English column mapping

## Forecast Engine â€” Pure JS (Feb 21, 2026)
- **Root cause of prod error**: Render `env: node` has no Python packages â†’ `spawn('python3', timemachine_forecast.py)` fails immediately with `ModuleNotFoundError`
- **Fix**: `web-ui/services/forecastEngine.js` â€” pure JS GBM/Monte Carlo (no Python)
  - DB price fetching via unified `db.all()` wrapper; PG uses `ANY($1)`, SQLite uses `IN (?,?,...)`
  - `yahoo-finance2` npm optional fallback for symbols not yet in DB
  - `simulateStock(symbol, amount, horizon, scenario, db)` â€” single stock
  - `autoSelectBest(amount, horizon, scenario, db)` â€” batch scan all 30 EGX30 stocks
- **Route**: `/forecast` in `timemachine.js` calls JS engine; `/simulate` (past backtest) still uses Python
- **Pattern**: `timemachine.js` now exports `{ router, attachDb }` like all other route modules; `server.js` calls `attachTimemachineDb(db, isPostgres)`
- **Committed**: `bd82e70`

## Time Machine Feature (Feb 18â€“28, 2026)
- **Past tab**: Python pipeline (ephemeral, no DB writes) â†’ `web-ui/routes/timemachine.js` spawns Python, Map cache 1h TTL
- **Future tab**: Monte Carlo GBM in `engines/timemachine_forecast.py`; auto-select best EGX30 stock via `_batch_prices_yfinance()` (single batch download); forecastEngine.js pure-JS fallback for prod
- **Key paths**: `engines/timemachine_data.py`, `engines/timemachine_signals.py`, `engines/timemachine_forecast.py`, `web-ui/routes/timemachine.js`, `web-ui/public/timemachine.js`, `web-ui/public/timemachine.css`
- **Delisted**: MNHD.CA, AUTO.CA removed; ALCN.CA, EAST.CA added as replacements
- **Prod fix**: `web-ui/requirements-web.txt` (minimal deps) + `pip3 install` in `render.yaml` for Render's Node env

## Custom News Sources (Feb 19, 2026)
- Admin panel `/admin`: "Custom News Sources" + "Manual Feed" sections
- `engines/custom_source_fetcher.py`: URL/RSS/public channel/bot/manual types
- DB: `custom_news_sources` + `custom_source_articles` (migration 011)
- SQLite: `NOW()` â†’ `datetime('now')`, datetime objects â†’ ISO strings via `_sanitize_params()`
- **UI rule**: Never display data-source provider names (no "Telegram", "Mubasher", etc.) anywhere in the public-facing UI

## GARCH + HMM Simulation Engine (Feb 28, 2026)
- `engines/garch_engine.py`: GARCH(1,1)/GJR/EGARCH per asset, AIC selection, residual correlation matrix
- `engines/regime_model.py`: K=2/3 HMM, BIC selection, Viterbi, Markov chain simulation
- `engines/simulation_core.py`: unified `SimulationEngine` with `SimulationConfig`
- Key bugs: `_fit_single_model` must NOT set `n_regimes`; `_nearest_psd` sanitize NaN/Inf; no Unicode in print() on Windows

## News RAG Integration (Mar 1, 2026)
- Full implementation in `news/` package â€” see `memory/news_rag.md` for details
- New DB tables: `news_rag_chunks`, `drift_adjustment_log` (migration 012)
- Node.js: 5 new endpoints in `web-ui/routes/rag.js` under `/api/rag/news/*` and `/api/rag/drift/*`
- `engines/simulation_core.py`: `_apply_news_drift_adjustments()` in `fit()` â€” graceful fallback
- New dep: `trafilatura>=1.8.0` (both requirements files)

## AI Research Assistant â€” EGX Knowledge (Mar 2, 2026)
- `web-ui/routes/rag.js` `/api/rag/chat` endpoint enriched with EGX context
- `EGX_MARKET_KNOWLEDGE` static block: market facts, trading hours (10:00â€“14:30 Cairo Sunâ€“Thu), currency (EGP), indices (EGX30/70/100), symbol format (TICKER.CA), regulator (FRA), 250+ companies, 15+ sectors
- Stock reference: queries `egx30_stocks` DB table (190 stocks: symbol, name_en, name_ar, sector_en) â†’ compact list injected into every chat prompt
- Graceful fallback: stock query wrapped in try/catch â€” if table missing (local SQLite), static EGX block still included
- Before: assistant said "I cannot provide information about comi.ca" â€” After: knows all 190 EGX stocks and basic market facts

## Walk-Forward Backtest Engine (Mar 16, 2026)
- `engines/walk_forward_backtest.py`: `WalkForwardBacktest` class â€” 90-day train / 20-day test / 10-day step rolling windows
  - Evaluates all 6 agents: consensus, ma, rsi, volume, ml, gemini
  - `_detect_postgres()` uses `'psycopg2' in module` only (not `'connection' in name` â€” matches SQLite too)
  - Idempotent upserts: `INSERT OR REPLACE` (SQLite) / `ON CONFLICT DO UPDATE` (PG)
  - Writes to `backtest_results` + `backtest_run_log` tables
- `run_backtest.py`: standalone entry point for GHA `weekly-backtest` job; auto-creates tables; per-symbol errors are non-fatal
- DB tables added: `backtest_results` (UNIQUE on symbol+agent_name+run_date), `backtest_run_log` (UNIQUE on run_date)
- API: `GET /api/track-record/backtest?agent=consensus` â†’ returns status 'pending' until first Sunday run

## Telegram Channel Ingestion (Mar 16, 2026)
- `engines/telegram_reader.py`: pulls posts from two public EGX channels; runs before agents in `run_agents.py`
  - Arabic/English parser: extracts tickers, direction (BULLISH/BEARISH/NEUTRAL), post_type (SIGNAL/NEWS/COMMENTARY), entry/target/stop prices
  - Session persisted in `system_config` DB table (base64-encoded .session file)
  - Non-fatal: any Telegram error is logged and swallowed â€” never crashes the main pipeline
  - First-run setup: `python engines/telegram_reader.py --setup` (interactive phone + OTP auth)
- EGX ticker whitelist: 30+ symbols in `EGX_TICKERS` set to reduce false-positive extractions
- New news columns: `ticker_mentions`, `direction`, `post_type`, `entry_price`, `target_price`, `stop_price`, `views`, `forwards`, `has_media`
- New DB table: `system_config (key PK, value TEXT, updated_at)` for session + other config storage
- `telethon>=1.42.0` added to `requirements.txt`

## Known Patterns
- Always check `db._isPostgres` for date/boolean/syntax differences between PG and SQLite
- Tab buttons need entries in both `TRANSLATIONS` and `applyLanguage()` loop
- CSS uses `var(--accent)` / `var(--accent-dark)` for brand gradient; `var(--card-bg)` / `var(--container-bg)` for surfaces
- Dark mode via `[data-theme="dark"]` on `:root`; RTL via `.rtl` class on `<html>`
- CDN libraries always wrapped with `typeof X !== 'undefined'` checks for graceful degradation
- Skeleton templates use `.skeleton-shimmer` base class + shape classes (`.skeleton-card`, `.skeleton-metric`, `.skeleton-chart`, `.skeleton-row`, `.skeleton-text`)
- Global utility functions in app.js: `escapeHtml()`, `animateValue()`, `showToast()`, `showSkeleton()`, `clearSkeleton()`, `renderEmptyState()` â€” all used by other modules via `typeof fn === 'function'` guards
## Docs Page RTL Sync (Mar 18, 2026)
- File: web-ui/public/docs.html
- Added robust language resolver: query param -> global localStorage('lang') -> docs fallback.
- Arabic mode now consistently applies RTL on /docs.
- Docs toggle now updates global language preference too for cross-page consistency.

## Adaptive Weighting + Change Intelligence (Mar 19, 2026)
- `run_agents.py`
  - upgraded adaptive agent weighting beyond simple 30d accuracy scaling.
  - weights now blend 30d/90d live win rate, recent alpha, sample-size shrinkage, and drift penalties.
  - added Consensus confidence calibration from evaluated historical outcomes.
  - added expected-edge estimation and ranking score for each latest consensus result.
- `database.py` and `web-ui/init-db.js`
  - added safe consensus columns:
    - `calibrated_confidence`
    - `expected_edge_pct`
    - `ranking_score`
    - `weight_profile_json`
    - `calibration_meta_json`
- `web-ui/server.js`
  - `/api/consensus` and `/api/consensus/:symbol` now enrich latest rows with calibrated confidence and expected edge.
  - added `/api/intelligence/changes` for:
    - signal changes vs previous consensus date
    - authenticated forecast deltas vs previous run
    - macro change markers from FX/regime history
  - added `/api/intelligence/quality` for:
    - freshness checks across prices/predictions/consensus/news/sentiment/FX/forecasts
    - drift monitoring from `agent_performance_daily`
- `web-ui/routes/rag.js`
  - added bilingual entity resolution for EGX stocks and ETFs via `egx30_stocks`, `instrument`, and `instrument_alias`.
  - chat retrieval now prioritizes resolved symbol/entity context and symbol-specific news before generic RAG excerpts.
  - `retrieval_meta` now includes resolved entities.
- Dashboard UI
  - `web-ui/public/index.html`, `web-ui/public/app.js`, `web-ui/public/style.css`
  - added â€œWhat Changed Todayâ€ and â€œFreshness & Driftâ€ section below the performance snapshot bar.
  - consensus cards now display calibrated confidence and expected edge.

## Mar 19, 2026 - Live Validation + Deploy
- Live smoke test passed against https://xmore-project.onrender.com after pushing main.
- Verified HTTP 200 for: /, /docs, /landing, /pro, /session, /track-record, /admin.
- Verified HTTP 200 for APIs: /api/consensus, /api/intelligence/changes, /api/intelligence/quality, /api/performance-v2/summary.
- Verified /api/consensus now returns calibrated_confidence, expected_edge_pct, and ranking_score.
- Verified /api/intelligence/changes returns signal, forecast, and macro change groups.
- Verified /api/intelligence/quality returns overall_status, freshness, and drift.
- Verified /api/rag/chat returns retrieval_meta.resolved_entities and sources on a live request.
- Validation also found and fixed pre-existing syntax errors in web-ui/public/performance-dashboard.js; npm run check now passes locally.

## Financial Audit Follow-Through (Mar 19, 2026)
- Kelly sizing is now active in the live recommendation pipeline:
  - `run_agents.py` applies Kelly sizing before execution realism.
  - `engines/execution_agent.py` blends volatility sizing with `kelly_position_pct`.
- Kelly sizing persistence/runtime fields were standardized:
  - `position_size_pct`
  - `volatility_position_pct`
  - `kelly_position_pct`
  - `shares_requested`
  - `shares_expected`
  - `position_sizing_mode`
  - plus execution realism cost/fill fields already persisted when schema supports them.
- `engines/kelly_allocator.py` now learns from resolved live `BUY` rows only, with symbol fallback to global stats and tighter exposure-cap enforcement.
- New friction-aware helper added:
  - `engines/backtest_friction.py`
  - used by both `engines/backtest.py` and `engines/walk_forward_backtest.py`
  - directional backtests now include fill ratio, slippage drag, and transaction cost drag.
- Public reporting is now net-first:
  - `web-ui/routes/performance.js`
  - `web-ui/routes/track-record.js`
  - gross metrics remain available as secondary context.
- `web-ui/public/track-record.js` copy was corrected to describe public performance metrics as net-of-transaction-cost metrics.
- Schema/bootstrap now includes the new execution + Kelly fields in:
  - `database.py`
  - `web-ui/init-db.js`
  - `migrations/add_execution_realism_columns.sql`
- `dashboard.py` execution-filter monitoring now reads the correct keys from `get_execution_filter_stats(...)`.
- Local verification completed:
  - Python compile checks on audit-touched engine/db/dashboard files passed.
  - `node --check` passed for performance/track-record/init-db JS files.
  - `python -m pytest tests/test_execution_realism.py -q` passed (`12 passed`).
- Remaining known gap:
  - stop-loss/gap-through-stop lifecycle simulation is still not a full explicit backtest execution model.
