# Xmore Project Memory

## Project Structure
- **Python backend**: data collection, ML agents, predictions (root level)
- **Node.js web UI**: `web-ui/` — Express server, API, dashboard
- **Database**: SQLite (local dev), PostgreSQL (production on Render)
- **Frontend**: Vanilla JS, CSS — bilingual EN/AR dashboard

## Key File Paths
- `web-ui/server.js` — Express app, all API endpoints
- `web-ui/init-db.js` — PostgreSQL table creation + full EGX stock seed (~190)
- `web-ui/middleware/auth.js` — JWT auth middleware
- `web-ui/routes/auth.js` — signup/login/logout/me
- `web-ui/routes/stocks.js` — GET /api/stocks
- `web-ui/routes/watchlist.js` — watchlist CRUD
- `web-ui/routes/trades.js` — trade recommendations + history
- `web-ui/routes/briefing.js` — daily briefing API (GET /api/briefing/today)
- `web-ui/public/app.js` — main dashboard logic (~1900+ lines)
- `web-ui/public/auth.js` — frontend auth module
- `web-ui/public/watchlist.js` — frontend watchlist module
- `web-ui/public/trades.js` — frontend trades/portfolio module
- `web-ui/public/briefing.js` — frontend briefing module (7-section dashboard)
- `web-ui/public/performance-dashboard.js` — performance metrics + equity curve
- `web-ui/public/style.css` — main CSS with CSS vars, responsive, RTL (~3050 lines)
- `web-ui/public/performance-dashboard.css` — performance tab styles
- `web-ui/public/auth.css` — auth modal + watchlist card styles
- `engines/briefing_generator.py` — pure computation: market pulse, sectors, risk, sentiment
- `engines/garch_engine.py` — GARCH/GJR-GARCH/EGARCH fitting + multivariate path simulation (Phase 1)
- `engines/regime_model.py` — Gaussian HMM regime detection + Markov path simulation (Phase 2)
- `engines/simulation_core.py` — unified SimulationEngine with SimulationConfig; backward-compatible simulate_paths()
- `engines/diagnostics.py` — GARCH + HMM + simulation output diagnostics (statistical tests + matplotlib plots)

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
- User watchlist (search, add/remove, no stock limit) — tab always visible, login prompt on click
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
- CDN: CountUp.js 2.8.0, Notyf 3.x, Lightweight Charts 4.1.1 — all with `typeof X !== 'undefined'` graceful fallback
- Global utils in app.js: `escapeHtml()`, `animateValue()`, `showToast()`, `showSkeleton()`, `clearSkeleton()`, `renderEmptyState()`

## CI/CD Pipeline (current — 7 jobs)
- **`intraday-price-update`**: `'0 7,8,9,10,11,12 * * 0-4'` (Sun–Thu, EGX hours) — `collect_data.py --prices-only`
- **`intraday-news-update`**: `'0 7,9,11 * * 0-4'` (3× trading day) — news + RSS + news RAG ingestion
- **`post-market-pipeline`**: `'30 12 * * 0-4'` — prices → news → sentiment → agents → evaluate (no continue-on-error!)
- **`egx-daily-snapshot`**: `'0 14 * * 0-4'` — backup EGX data export
- **`daily-pipeline`**: `'0 22 * * 0-5'` (Sun–Fri) — full: collect → agents → portfolios → evaluate; depends on post-market-pipeline but runs anyway (`if: always()`)
- **`catchup-evaluation`**: `'0 6,12,18 * * *'` (3× daily) — `evaluate.py` + `evaluate_performance.py`
- **`weekly-backtest`**: `'0 7 * * 0'` (Sunday 07:00 UTC = 09:00 Cairo) — `run_backtest.py` walk-forward validation
- **Key Python files**: `collect_data.py`, `sentiment_gemini.py`, `run_agents.py`, `evaluate.py`, `engines/evaluate_performance.py`, `engines/generate_portfolios.py`
- **Required secrets**: `DATABASE_URL`, `FINNHUB_API_KEY`, `NEWS_API_KEY`, `GOOGLE_API_KEY`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- **Concurrency**: `cancel-in-progress: false` — new runs queue behind running ones; earlier queued runs can be dropped
- **EGX price source**: `data/egx_live_scraper.py` (primary, `http://41.33.162.236/egs4/`) → yfinance fallback (`.CA` suffix)

## ML Agent Improvements (Mar 11, 2026)
- **LightGBM** replaces RandomForestClassifier in `agents/agent_ml.py`; RF fallback if not installed
  - `class_weight='balanced'` handles UP/DOWN minority vs FLAT majority imbalance
  - Two-pass training: WFV (5 folds) → feature selection by gain importance → retrain on all data
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
- **Vol regime thresholds** (shared): EWMA span=32, daily — Low <1.5%, High >3.0%, Normal otherwise
- **GARCH-inspired features** in `features.py`: `garch_ewm_vol`, `vol_of_vol`, `vol_persistence` (no arch lib needed)
- **Macro features**: `brent_return_5d`, `usdegp_return_5d`, `eem_return_5d` — stored as MACRO_* in prices table, 5d pct_change
- **USD/EGP source** (`collect_data.py` `_fetch_usdegp_rate()`): CBE official (cbe.org.eg) primary → open.er-api.com → frankfurter.app → exchangerate.host → yfinance fallback. CBE blocked by WAF on cloud IPs; free APIs cover Render. `data_source='cbe_official'` when CBE succeeds.
- **Session Sheet** (`/session`, `web-ui/public/session.html`+`session.css`):
  - Stock table: CODE, Name, Trend (صاعد/عرضى/هابط), Type (متاجرة/احتفاظ), Buy Guide, Stop Loss, Target, Profit%, Risk%, R/R, S2, S1, Pivot, R1, R2
  - Index cards: EGX30/70 pivot levels computed server-side from last 2 OHLC rows
  - API: `GET /api/trades/session-sheet` → `{session_date, stocks[], indices[]}`
  - `engines/pivot_engine.py`: classic floor-trader pivots, ATR(14), EMA10/30 trend, buy guide at S1
  - 10 new columns in `trade_recommendations` (safe-add migration): trend_ar/en, rec_type_ar/en, buy_guide, pivot, r1, r2, s1, s2
  - `get_ohlc_df(symbol, limit=60)` in `run_agents.py`; `enrich_recommendation()` called after risk levels
- **Landing page** (`/landing`, `web-ui/public/landing.html`): pitch, why Xmore, customer, problem, how it works, edge
- **HOLD eval fix** (`evaluate.py`): `abs(pct_change) < 2.0` (was `actual_outcome == "FLAT"` at ±0.5%)
- **Dynamic agent weights** (`run_agents.py`): accuracy-adjusted via `agent_performance_daily` (PG only)
- **GARCH in risk agent** (`risk_agent.py`): `garch_forecast_vol` preferred over `volatility_20d`
- **High-impact ML improvements** (Mar 2026):
  - **Per-symbol LightGBM models**: `models/{SYMBOL}_predictor.pkl`; in-memory `_model_cache`; global fallback for thin data
  - **Confidence gating**: `CONFIDENCE_THRESHOLD=0.60`; UP/DOWN→HOLD when `max(probs)<0.60`
  - **Optuna HPO**: 25-trial TPE, cached in model file (`best_params` key); skipped on retrains
  - **Regime-gated consensus** (Layer 4 in `consensus_engine.py`): Crisis→UP blocked; Turbulent→conviction downgraded
  - **`_detect_market_regime()`** in `run_agents.py`: tries EGX30.CA → COMI.CA → HRHO.CA as HMM proxy

## Bug Fixes — see `memory/bugfixes.md` for full details
- **Feb 2026**: PG `_safe_add_column()`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`, `utils.py` shadowing `utils/` package
- **Mar 2, 2026**: Three fixes pushed — see bugfixes.md for details:
  1. `evaluate.py`: `r.ok = 1` → `r.ok = TRUE` (PG BOOLEAN type mismatch, was breaking daily pipeline)
  2. `app.js formatDate()`: now strips ISO timestamp to `YYYY-MM-DD` — fixes "02:00" display on date cards
  3. `data/egx_live_scraper.py`: `df.loc[:, ~df.columns.duplicated()]` after rename — fixes "truth value of a Series is ambiguous" from duplicate Arabic→English column mapping

## Forecast Engine — Pure JS (Feb 21, 2026)
- **Root cause of prod error**: Render `env: node` has no Python packages → `spawn('python3', timemachine_forecast.py)` fails immediately with `ModuleNotFoundError`
- **Fix**: `web-ui/services/forecastEngine.js` — pure JS GBM/Monte Carlo (no Python)
  - DB price fetching via unified `db.all()` wrapper; PG uses `ANY($1)`, SQLite uses `IN (?,?,...)`
  - `yahoo-finance2` npm optional fallback for symbols not yet in DB
  - `simulateStock(symbol, amount, horizon, scenario, db)` — single stock
  - `autoSelectBest(amount, horizon, scenario, db)` — batch scan all 30 EGX30 stocks
- **Route**: `/forecast` in `timemachine.js` calls JS engine; `/simulate` (past backtest) still uses Python
- **Pattern**: `timemachine.js` now exports `{ router, attachDb }` like all other route modules; `server.js` calls `attachTimemachineDb(db, isPostgres)`
- **Committed**: `bd82e70`

## Time Machine Feature (Feb 18–28, 2026)
- **Past tab**: Python pipeline (ephemeral, no DB writes) → `web-ui/routes/timemachine.js` spawns Python, Map cache 1h TTL
- **Future tab**: Monte Carlo GBM in `engines/timemachine_forecast.py`; auto-select best EGX30 stock via `_batch_prices_yfinance()` (single batch download); forecastEngine.js pure-JS fallback for prod
- **Key paths**: `engines/timemachine_data.py`, `engines/timemachine_signals.py`, `engines/timemachine_forecast.py`, `web-ui/routes/timemachine.js`, `web-ui/public/timemachine.js`, `web-ui/public/timemachine.css`
- **Delisted**: MNHD.CA, AUTO.CA removed; ALCN.CA, EAST.CA added as replacements
- **Prod fix**: `web-ui/requirements-web.txt` (minimal deps) + `pip3 install` in `render.yaml` for Render's Node env

## Custom News Sources (Feb 19, 2026)
- Admin panel `/admin`: "Custom News Sources" + "Manual Feed" sections
- `engines/custom_source_fetcher.py`: URL/RSS/public channel/bot/manual types
- DB: `custom_news_sources` + `custom_source_articles` (migration 011)
- SQLite: `NOW()` → `datetime('now')`, datetime objects → ISO strings via `_sanitize_params()`
- **UI rule**: Never display data-source provider names (no "Telegram", "Mubasher", etc.) anywhere in the public-facing UI

## GARCH + HMM Simulation Engine (Feb 28, 2026)
- `engines/garch_engine.py`: GARCH(1,1)/GJR/EGARCH per asset, AIC selection, residual correlation matrix
- `engines/regime_model.py`: K=2/3 HMM, BIC selection, Viterbi, Markov chain simulation
- `engines/simulation_core.py`: unified `SimulationEngine` with `SimulationConfig`
- Key bugs: `_fit_single_model` must NOT set `n_regimes`; `_nearest_psd` sanitize NaN/Inf; no Unicode in print() on Windows

## News RAG Integration (Mar 1, 2026)
- Full implementation in `news/` package — see `memory/news_rag.md` for details
- New DB tables: `news_rag_chunks`, `drift_adjustment_log` (migration 012)
- Node.js: 5 new endpoints in `web-ui/routes/rag.js` under `/api/rag/news/*` and `/api/rag/drift/*`
- `engines/simulation_core.py`: `_apply_news_drift_adjustments()` in `fit()` — graceful fallback
- New dep: `trafilatura>=1.8.0` (both requirements files)

## AI Research Assistant — EGX Knowledge (Mar 2, 2026)
- `web-ui/routes/rag.js` `/api/rag/chat` endpoint enriched with EGX context
- `EGX_MARKET_KNOWLEDGE` static block: market facts, trading hours (10:00–14:30 Cairo Sun–Thu), currency (EGP), indices (EGX30/70/100), symbol format (TICKER.CA), regulator (FRA), 250+ companies, 15+ sectors
- Stock reference: queries `egx30_stocks` DB table (190 stocks: symbol, name_en, name_ar, sector_en) → compact list injected into every chat prompt
- Graceful fallback: stock query wrapped in try/catch — if table missing (local SQLite), static EGX block still included
- Before: assistant said "I cannot provide information about comi.ca" — After: knows all 190 EGX stocks and basic market facts

## Walk-Forward Backtest Engine (Mar 16, 2026)
- `engines/walk_forward_backtest.py`: `WalkForwardBacktest` class — 90-day train / 20-day test / 10-day step rolling windows
  - Evaluates all 6 agents: consensus, ma, rsi, volume, ml, gemini
  - `_detect_postgres()` uses `'psycopg2' in module` only (not `'connection' in name` — matches SQLite too)
  - Idempotent upserts: `INSERT OR REPLACE` (SQLite) / `ON CONFLICT DO UPDATE` (PG)
  - Writes to `backtest_results` + `backtest_run_log` tables
- `run_backtest.py`: standalone entry point for GHA `weekly-backtest` job; auto-creates tables; per-symbol errors are non-fatal
- DB tables added: `backtest_results` (UNIQUE on symbol+agent_name+run_date), `backtest_run_log` (UNIQUE on run_date)
- API: `GET /api/track-record/backtest?agent=consensus` → returns status 'pending' until first Sunday run

## Telegram Channel Ingestion (Mar 16, 2026)
- `engines/telegram_reader.py`: pulls posts from two public EGX channels; runs before agents in `run_agents.py`
  - Arabic/English parser: extracts tickers, direction (BULLISH/BEARISH/NEUTRAL), post_type (SIGNAL/NEWS/COMMENTARY), entry/target/stop prices
  - Session persisted in `system_config` DB table (base64-encoded .session file)
  - Non-fatal: any Telegram error is logged and swallowed — never crashes the main pipeline
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
- Global utility functions in app.js: `escapeHtml()`, `animateValue()`, `showToast()`, `showSkeleton()`, `clearSkeleton()`, `renderEmptyState()` — all used by other modules via `typeof fn === 'function'` guards
