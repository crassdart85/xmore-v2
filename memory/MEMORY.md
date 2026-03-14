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

## CI/CD Pipeline (current — 6 jobs, concurrency group `trading-pipeline`)
- **`intraday-price-update`**: `'0 7,8,9,10,11,12 * * 0-4'` (Sun–Thu, EGX hours) — `collect_data.py --prices-only`
- **`intraday-news-update`**: `'0 7,9,11 * * 0-4'` (3× trading day) — news + RSS + news RAG ingestion
- **`post-market-pipeline`**: `'30 12 * * 0-4'` — prices → news → sentiment → agents → evaluate (no continue-on-error!)
- **`egx-daily-snapshot`**: `'0 14 * * 0-4'` — backup EGX data export
- **`daily-pipeline`**: `'0 22 * * 0-5'` (Sun–Fri) — full: collect → agents → portfolios → evaluate; depends on post-market-pipeline but runs anyway (`if: always()`)
- **`catchup-evaluation`**: `'0 6,12,18 * * *'` (3× daily) — `evaluate.py` + `evaluate_performance.py`
- **Key Python files**: `collect_data.py`, `sentiment_gemini.py`, `run_agents.py`, `evaluate.py`, `engines/evaluate_performance.py`, `engines/generate_portfolios.py`
- **Required secrets**: `DATABASE_URL`, `FINNHUB_API_KEY`, `NEWS_API_KEY`, `GOOGLE_API_KEY`
- **Concurrency**: `cancel-in-progress: false` — new runs queue behind running ones; earlier queued runs can be dropped
- **EGX price source**: `data/egx_live_scraper.py` (primary, `http://41.33.162.236/egs4/`) → yfinance fallback (`.CA` suffix)

## Bug Fixes — see `memory/bugfixes.md` for full details
- **Feb 2026**: PG `_safe_add_column()`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`, `utils.py` shadowing `utils/` package
- **Mar 2, 2026**: Three fixes pushed — see bugfixes.md for details:
  1. `evaluate.py`: `r.ok = 1` → `r.ok = TRUE` (PG BOOLEAN type mismatch, was breaking daily pipeline)
  2. `app.js formatDate()`: now strips ISO timestamp to `YYYY-MM-DD` — fixes "02:00" display on date cards
  3. `data/egx_live_scraper.py`: `df.loc[:, ~df.columns.duplicated()]` after rename — fixes "truth value of a Series is ambiguous" from duplicate Arabic→English column mapping
 
## Mar 14, 2026 — UI/Deploy Fixes
- **Render boot crash**: fixed a duplicate `catch` block in `web-ui/routes/performance.js` that caused `SyntaxError: missing ) after argument list` on startup.
- **Header cleanup**: removed absolute positioning from header controls and user info bar to prevent overlap; tightened small-screen behavior in `web-ui/public/style.css` + `web-ui/public/auth.css`.
- **Snapshot bar**: removed “Live-Only Data” pill from the global performance snapshot bar (`web-ui/public/app.js`, `web-ui/public/style.css`).

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
- Admin panel `/admin`: "Custom News Sources" + "Telegram Manual Feed" sections
- `engines/custom_source_fetcher.py`: URL/RSS/Telegram public/bot/manual types
- DB: `custom_news_sources` + `custom_source_articles` (migration 011)
- SQLite: `NOW()` → `datetime('now')`, datetime objects → ISO strings via `_sanitize_params()`

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

## Known Patterns
- Always check `db._isPostgres` for date/boolean/syntax differences between PG and SQLite
- Tab buttons need entries in both `TRANSLATIONS` and `applyLanguage()` loop
- CSS uses `var(--accent)` / `var(--accent-dark)` for brand gradient; `var(--card-bg)` / `var(--container-bg)` for surfaces
- Dark mode via `[data-theme="dark"]` on `:root`; RTL via `.rtl` class on `<html>`
- CDN libraries always wrapped with `typeof X !== 'undefined'` checks for graceful degradation
- Skeleton templates use `.skeleton-shimmer` base class + shape classes (`.skeleton-card`, `.skeleton-metric`, `.skeleton-chart`, `.skeleton-row`, `.skeleton-text`)
- Global utility functions in app.js: `escapeHtml()`, `animateValue()`, `showToast()`, `showSkeleton()`, `clearSkeleton()`, `renderEmptyState()` — all used by other modules via `typeof fn === 'function'` guards
