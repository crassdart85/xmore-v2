# Xmore Project Memory

## Project Overview
Stock trading prediction system with web dashboard. Uses multiple AI agents to predict stock movements.

**Last Updated**: March 25, 2026

## Mar 25, 2026 - KSA Production Crash Hardening
- Fixed a production crash class on the KSA deployment where the unified DB adapter in `web-ui/server.js` only supported callback-style usage, but several KSA routes were using `await db.all(...)` / `await db.get(...)`.
- Hardened `web-ui/server.js` so both PostgreSQL and SQLite adapters now support:
  - callback style: `db.all(query, params, cb)`
  - promise style: `await db.all(query, params)`
- This prevents `TypeError: callback is not a function` from crashing the process when a route uses promise-style access.
- Also hardened:
  - `web-ui/middleware/auth.js`
    - production fallback secret is now stable-derived instead of ephemeral, so missing `JWT_SECRET` no longer invalidates sessions on every restart
  - `web-ui/init-db-ksa.js`
    - shared tables now backfill `market_id` with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` before creating KSA market-scoped indexes
- Operational rule:
  - the shared DB adapter must be treated as dual-mode going forward because the KSA codebase already mixes callback and async/await route styles

## Mar 25, 2026 - KSA Time Machine UI Alignment
- Fixed KSA Time Machine user-facing leakage where the UI was still exposing EGX-era wording and benchmark field names.
- Updated KSA Time Machine UI in:
  - `web-ui/public/app.js`
  - `web-ui/public/timemachine.js`
  - `web-ui/routes/timemachine.js`
  - `engines/timemachine.py`
- Changes:
  - investment amount labels and validation copy now use `SAR` / `ريال`
  - Time Machine subtitle keeps TASI framing without user-visible EGX wording
  - frontend now normalizes legacy benchmark payload fields like `egx30_value` / `egx30_return_pct` into a benchmark/TASI view before rendering charts and tables
  - simulation validation and server-side logs now refer to SAR instead of EGP
- Operational rule:
  - for KSA deployment UI, payload compatibility with legacy field names is acceptable internally, but user-visible labels must always present TASI/SAR terminology

## Mar 25, 2026 - KSA Track Record Route + API Alignment
- Found that the KSA deployment was serving the generic `/track-record` page, which is wired to EGX endpoints and showed EGX data on `xmore-ksa.onrender.com`.
- Fixed KSA track record routing and data wiring:
  - `web-ui/server.js`
    - `/track-record` now redirects to `/ksa/track-record` on the KSA deployment
  - `web-ui/public/ksa-track-record.js`
    - switched data fetches from missing `/api/ksa/performance/*` paths to implemented `/api/ksa/track-record/*` paths
  - `web-ui/routes/ksa-signals.js`
  - `web-ui/routes/ksa-track-record.js`
    - replaced invalid `await db.all(...)` / `await db.get(...)` usage with local promise wrappers around the callback-style DB adapter from `server.js`
- Result:
  - the public KSA track record route now points at the KSA page instead of the EGX page
  - KSA API handlers no longer fail just because of callback/promise mismatch
- Operational rule:
  - on the KSA deployment, never point `/track-record` at the generic EGX page
  - route handlers mounted under Express must match the callback-style DB adapter unless they explicitly wrap it in promises

## Mar 25, 2026 - Full Branch Validation + Live Production Smoke
- Verified current branch heads:
  - `main` at `ac0d2ef20d2a4b649e16dfbe18a9c5f2ebfc6cda`
  - `xmore-ksa` at `bf2fe8fb9d3b5a8e04bad4aab1c09bf92b78f53e`
- Local validation passed on both branches:
  - `npm run check`
  - `pytest` -> `52 passed`
- Live production smoke passed against both deployments:
  - `https://xmore-project.onrender.com`
  - `https://xmore-ksa.onrender.com`
- Confirmed production endpoints returning data:
  - `/api/performance-v2/export-summary`
  - `/api/intelligence/changes`
- Operational note:
  - `main` does not currently define npm script `smoke:url`
  - the KSA branch smoke runner successfully validated both deployed URLs
- Known live behavior:
  - `/api/health` returns `404` on both deployments because no health route is currently implemented

## Mar 25, 2026 - KSA Workflow Runtime CLI Alignment
- GitHub was accepting the current workflow YAML, but several KSA jobs still failed because workflow commands passed unsupported market flags into branch-specialized scripts.
- Fixed `.github/workflows/ksa-daily-pipeline.yml` so the runtime commands now match the actual KSA branch CLIs:
  - removed unsupported `--market KSA` from `collect_data.py`
  - removed unsupported `--market KSA` from `evaluate.py`
  - removed unsupported `--market KSA` from `news/ingest_cli.py`
  - removed unsupported `--market KSA` from `sentiment_gemini.py`
  - removed unsupported `--market KSA` from `engines/generate_portfolios.py`
  - changed `python agents/dcf/ksa_dcf_engine.py --force` to `python -m agents.dcf.ksa_dcf_engine --force`
- Operational rule:
  - this branch already encodes KSA behavior in many entry points, so avoid adding `--market KSA` unless the parser explicitly supports it
  - prefer module execution for package-based scripts inside CI when import resolution depends on repo-root Python package loading

## Mar 25, 2026 - Workflow Branch Alignment
- Fixed GitHub Actions checkout behavior in KSA workflow files:
  - `.github/workflows/ksa-daily-pipeline.yml`
  - `.github/workflows/scheduled-tasks.yml`
  - `.github/workflows/backfill-predictions.yml`
  - `.github/workflows/run-backtest.yml`
- Replaced hard-coded refs (`main`, `xmore-ksa`) with `${{ github.ref_name }}` so manual runs execute the actual triggering branch.
- Important GitHub limitation:
  - scheduled workflows only run from the repository default branch
  - KSA cron execution is therefore dispatched from `main` via `.github/workflows/ksa-branch-scheduled.yml`, which checks out `xmore-ksa`
- Operational rule:
  - keep branch-local KSA workflows branch-aware for manual runs
  - keep default-branch KSA scheduling in sync with `xmore-ksa` workflow logic

## Mar 25, 2026 - Performance Metrics EGX Basis Fix
- Fixed `engines/performance_metrics.py` to stop inheriting KSA compatibility aliases for EGX Sharpe/Sortino/reporting defaults.
- EGX reporting constants are now explicit in the metrics module:
  - `EGX_RISK_FREE_RATE_ANNUAL = 0.2725`
  - `EGX_TRADING_DAYS_PER_YEAR = 247`
- `EGX_ROUND_TRIP_RATE` remains imported from execution config.
- Result:
  - shared performance-metrics test suite now passes on `xmore-ksa`
  - branch verification is green across frontend checks, Python compile checks, and `pytest`

## Mar 20, 2026 — Hamburger Menu Cleanup + Time Machine Validation
- **Hamburger menu icon removal**: Stripped all emoji icon prefixes from mobile menu items across all 6 pages (`landing.html`, `session.html`, `pro.html`, `track-record.html`, `index.html`, `docs.html`)
- **pro.html ID case bug fixed**: HTML had `ProMobileMenuBtn`/`ProMobileMenuDropdown` (capital P) but `Pro.js` queries `proMobileMenuBtn`/`proMobileMenuDropdown` (lowercase p) — menu was silently broken; fixed HTML IDs to match JS
- **index.html encoding fixed**: Hamburger `☰` was stored as mojibake `â˜°`; fixed via Unicode codepoint replacement. All menu item emoji prefixes stripped with targeted regex
- **docs.html active-class variant**: Required `class="mobile-menu-item[^"]*"` regex pattern (instead of exact match) to handle `mobile-menu-item active` class on the current-page item
- **Time Machine fully validated (live)**:
  - `POST /api/timemachine/simulate` → 200 OK (equity_curve 295 pts, `total_return_pct=8.18`)
  - `POST /api/timemachine/forecast` (COMI, 30d base) → 200 OK (+11.48%, 76.5% prob positive)
  - `POST /api/timemachine/forecast` (auto) → 200 OK (ABUK.CA auto-selected, +32.01%, 93.6%)
- **Known issues (not fixed this session)**:
  - `web-ui/routes/track-record.js`: `SQLITE_ERROR: no such column: round_trip_cost_egp` — local SQLite schema outdated
  - `yahoo-finance2` CJS fallback broken on Node v22 (forecast uses DB data, not live feed — non-blocking)

## Deployment Architecture
- **Render.com** - Hosts web dashboard + PostgreSQL database
- **GitHub Actions** - Runs scheduled automation tasks
- **GitHub** - Source code repository

## Key Files
- `engines/trade_recommender.py` - Daily trade signal generator (Phase 2)
- `engines/evaluate_performance.py` - **NEW** Performance evaluation engine (replaces `evaluate_trades.py`)
- `engines/performance_metrics.py` - **NEW** Professional financial metrics calculator (Sharpe, alpha, drawdown)
- `engines/briefing_generator.py` - Daily market briefing generator (now includes track record snippet)
- `engines/portfolio_config.py` - **NEW** Portfolio archetype configurations (Conservative/Balanced/Aggressive)
- `engines/portfolio_engine.py` - **NEW** Signal-to-allocation pipeline (5-step: collect ? filter ? score ? allocate ? publish)
- `engines/circuit_breaker.py` - **NEW** Drawdown circuit breaker (increases cash when drawdown exceeds threshold)
- `engines/generate_portfolios.py` - **NEW** Cron orchestrator for portfolio generation (runs after daily predictions)
- `evaluate_trades.py` - Trade recommendation accuracy tracker (legacy â€” superseded by `evaluate_performance.py`)
- `web-ui/routes/trades.js` - API routes for trades and portfolio
- `web-ui/routes/performance.js` - **NEW** Investor-grade performance API routes (`/api/performance-v2/*`)
- `web-ui/public/trades.js` - Frontend logic for trades dashboard
- `web-ui/public/performance-dashboard.js` - **NEW** Performance dashboard UI (canvas chart, agent table, audit modal)
- `web-ui/public/performance-dashboard.css` - **NEW** Performance dashboard styling (dark/light, RTL, responsive)
- `web-ui/public/app.js` - Frontend JavaScript (tabs, TradingView, bilingual)
- `web-ui/public/style.css` - Dashboard styling with tabs, RTL, responsive
- `web-ui/public/index.html` - Dashboard HTML (tabs, TradingView ticker, performance section)
- `web-ui/server.js` - Express API server (SQLite local, PostgreSQL production)
- `web-ui/migrations/007_performance_benchmark.sql` - **NEW** Performance schema migration
- `web-ui/migrations/008_model_portfolios.sql` - **NEW** Portfolio tables migration (model_portfolios, portfolio_allocations, portfolio_performance)
- `sentiment.py` - Finnhub news + FinBERT + VADER dual-engine sentiment
- `features.py` - 40+ TA-Lib technical indicators with pure Python fallback
- `data/egx_live_scraper.py` - EGX live feed scraper with yfinance fallback
- `data/egx_name_mapping.py` - Bilingual company name auto-generator
- `agents/agent_consensus.py` - Accuracy-weighted consensus voting agent
- `database.py` - Database connection + table creation (now includes performance tables)
- `TERMS.md` - Legal terms of service
- `docs/PERFORMANCE_SYSTEM.md` - **NEW** Performance system architecture document
- `render.yaml` - Render deployment configuration
- `.github/workflows/scheduled-tasks.yml` - GitHub Actions automation
- `tests/test_portfolio_engine.py` - **NEW** Portfolio engine unit tests (constraints, allocation math, edge cases)
- `stocks.db` - SQLite database (local only)

## GitHub Actions Schedule
| Task | Schedule | Script |
|------|----------|---------|
| EGX Data Collection | Sun-Thu 12:30 PM EST | `collect_data.py` (EGX live â†’ yfinance) |
| US Data + Sentiment | Mon-Fri 4:30 PM EST | `collect_data.py` + `sentiment.py` |
| Predictions | Sun-Fri 5:00 PM EST (daily, 1-day) | `run_agents.py` (incl. Consensus, Trades, Performance Eval) |
| Portfolio Generation | Daily (after predictions) | `engines/generate_portfolios.py` (needs: daily-predictions) |
| Performance Eval | Daily (Step 8 in pipeline) | `engines/evaluate_performance.py` (called by `run_agents.py`) |
| Evaluation | Every hour | `evaluate.py` |

> **Note (Feb 2026):** Predictions changed from weekly (7-day) to daily (1-day) horizon for faster evaluation turnaround. GitHub Actions checkout upgraded to `actions/checkout@v4` with explicit `ref: main` and `fetch-depth: 1`.

## Environment Variables (Secrets)
- `DATABASE_URL` - PostgreSQL connection string (Render)
- `JWT_SECRET` - JWT signing secret for auth cookies (required for stable sessions in production)
- `NEWS_API_KEY` - News API for news collection
- `FINNHUB_API_KEY` - Finnhub API for sentiment analysis news

## Tech Stack
- **Backend**: Node.js/Express (web-ui), Python (agents)
- **Database**: SQLite (local), PostgreSQL (production/Render)
- **Frontend**: Vanilla JS, CSS with animations
- **CI/CD**: GitHub Actions (`actions/checkout@v4`), Render auto-deploy

## Agents
- `MA_Crossover_Agent` - Moving average trend analysis
- `ML_RandomForest` - Machine learning with 40+ TA-Lib features, walk-forward validation
- `RSI_Agent` - Momentum indicator (RSI)
- `Volume_Spike_Agent` - Volume analysis
- `Consensus` - Accuracy-weighted vote across all agents (Phase 1)
- **Trade Recommendation Engine** - Generates actionable Buy/Sell signals with entry/exit targets (Phase 2)
- **Performance Evaluation Engine** - Resolves outcomes, calculates alpha vs EGX30 benchmark, agent accuracy snapshots (Phase 3)

## UI Features (Updated Feb 2026)
1. **Tab Navigation** - Predictions, Performance, Results, Prices tabs
2. **Performance Dashboard (v2)** - Investor-grade dashboard with key metrics cards, equity curve chart, agent accuracy table, best/worst stocks, recent predictions, rolling windows, integrity section, and audit log modal
3. **TradingView Ticker Tape** - Live EGX30 + major stocks at top
4. **TradingView Mini Charts** - Lazy-loaded per-stock charts (click to load)
5. **Signal Terminology** - "Bullish/Bearish/Neutral" instead of "UP/DOWN/HOLD"
6. **Agent Accuracy Badges** - Per-agent accuracy shown on prediction cards
7. **Consensus Signal** - Weighted vote with agreement indicator
8. **Bilingual Disclaimers** - EN + AR legal disclaimers in footer, Terms link
9. **Dark Mode** - Toggle via header button, system preference detection
10. **Bilingual Support (EN/AR)** - Language switcher with RTL support
11. **Grouped Predictions** - Stock shown once with rowspan for multiple agents
12. **Agent Tooltips** - Hover descriptions explaining each agent (bilingual)
13. **Company Name Mapping** - US and EGX stocks with full names (bilingual)
14. **Color-coded Accuracy** - Green (60%+), Yellow (40-60%), Red (<40%)
15. **Responsive Design** - Breakpoints: 1024px, 768px, 480px, 360px
16. **Sentiment Badges** - Bullish/Neutral/Bearish badges per stock
17. **Print Styles** - Clean printing without TradingView/tabs/buttons
18. **Skeleton Loader** - Animated placeholder rows while predictions load
19. **Parallel Data Loading** - All API calls fire simultaneously on page load
20. **Trades Dashboard** - "Today's Recommendations" tab with actionable signals (Phase 2)
21. **Portfolio Tracker** - "Portfolio" tab showing open positions and history (Phase 2)
22. **Trade Cards** - detailed visual cards with Conviction, R/R ratio, and bilingual reasoning
23. **Portfolio Performance** - Real-time P&L tracking for virtual portfolio
24. **Equity Curve Chart** - Canvas-rendered cumulative return chart (Xmore vs EGX30 benchmark) with period selector
25. **Agent Accuracy Table** - Per-agent 30d/90d win rate, predictions count, avg confidence
26. **Audit Trail Modal** - View all prediction modification logs for full transparency
27. **Integrity Section** - Immutability status, audit trail, live-only indicator, minimum threshold progress

## Sentiment Analysis (Phase 1 Upgrade)
- **Dual Engine**: VADER (fast, 1000+ headlines/sec) + FinBERT (deep accuracy)
- **Auto Mode**: VADER for >50 headlines, FinBERT for smaller batches
- **Source Weighting**: Bloomberg/Reuters prioritized over generic news
- **Source**: Finnhub API for company news
- **Storage**: `sentiment_scores` table with avg_sentiment, label, article counts
- **Integration**: Agents receive sentiment data to confirm/adjust signals
- **Display**: Color-coded badges (green=Bullish, gray=Neutral, red=Bearish)
- **API**: `/api/sentiment` endpoint returns latest sentiment per stock

## API Endpoints
- `/api/predictions` - Latest predictions from all agents (includes disclaimer)
- `/api/performance` - Agent accuracy statistics (legacy)
- `/api/performance/detailed` - Full breakdown (per-agent, per-stock, monthly trend) (legacy)
- `/api/performance-v2/summary` - **NEW** Investor-grade overall performance + rolling metrics
- `/api/performance-v2/by-agent` - **NEW** Per-agent accuracy comparison (latest daily snapshot)
- `/api/performance-v2/by-stock?days=N` - **NEW** Per-stock performance breakdown
- `/api/performance-v2/equity-curve?days=N` - **NEW** Cumulative return series (Xmore vs EGX30)
- `/api/performance-v2/predictions/open` - **NEW** Currently open (unresolved) predictions
- `/api/performance-v2/predictions/history?page=N&limit=N` - **NEW** Auditable prediction history
- `/api/performance-v2/audit?limit=N` - **NEW** Prediction modification audit trail
- `/api/evaluations` - Prediction results (predicted vs actual)
- `/api/sentiment` - Latest sentiment scores per stock
- `/api/prices` - Latest stock prices
- `/api/trades/today` - Today's active trade recommendations
- `/api/trades/history` - Historical trade recommendations
- `/api/portfolio` - User portfolio (open positions, performance stats)
- `/api/stats` - System statistics

### Portfolio Endpoints (Phase 2 — Planned)
- `GET /api/portfolios` - List portfolio types with latest snapshot
- `GET /api/portfolios/:type` - Full allocation detail for a portfolio type (preview: free / full: auth)
- `GET /api/portfolios/:type/performance` - Historical performance + metrics
- `GET /api/portfolios/:type/history` - All past snapshots and rebalances (auth)
- `GET /api/portfolios/:type/compare` - Side-by-side with EGX30
- `POST /api/portfolios/simulate` - Simulate allocation with custom amount (auth)
- `GET /api/portfolios/changes` - Latest rebalance changes (auth)

## Common Tasks
**Local Development:**
- Start server: `cd web-ui && npm install && node server.js`
- Run agents: `python run_agents.py` (includes performance evaluation as Step 8)
- Evaluate predictions: `python evaluate.py`
- Evaluate performance: `python -c "from engines.evaluate_performance import run_evaluation; run_evaluation()"`
- Generate portfolios: `python engines/generate_portfolios.py`
- Run portfolio tests: `python -m pytest tests/test_portfolio_engine.py -v`
- Evaluate trades (legacy): `python evaluate_trades.py`
- Collect data: `python collect_data.py`
- Collect sentiment: `python sentiment.py` (requires FINNHUB_API_KEY)

**Production (Render):**
- Auto-deploys on push to main branch
- Dashboard: trading-dashboard service
- Database: trading-db PostgreSQL

## Troubleshooting
- **"Performance tracking will begin..."** - Normal message when no evaluations exist yet. Wait for hourly GitHub Action
- **"N/A" sentiment badges** - Run `python sentiment.py` or check FINNHUB_API_KEY secret
- **Server errors** - Run `npm install` in web-ui folder, then restart server
- **Browser cache** - Hard refresh (Ctrl+Shift+R) after code changes; static assets use `?v=` cache-busting
- **GitHub Actions failing** - Check secrets: DATABASE_URL, NEWS_API_KEY, FINNHUB_API_KEY
- **Render not updating** - Wait 2-3 minutes after push for auto-deploy
- **Blank dashboard / no data** - Check browser console for JS errors; `window.onerror` handler shows errors on-page

## Database Tables

### Core Tables
| Table | Purpose |
|-------|---------|
| `prices` | Historical OHLCV data |
| `news` | News articles with sentiment |
| `predictions` | Per-agent predictions |
| `consensus_results` | Consensus engine output |
| `evaluations` | Prediction outcomes |
| `sentiment_scores` | Aggregated sentiment |
| `trade_recommendations` | Daily trade signals |
| `user_positions` | Virtual portfolio positions |
| `daily_briefings` | Generated daily briefings |
| `prediction_audit_log` | **NEW** Audit trail for outcome changes |
| `agent_performance_daily` | **NEW** Per-agent rolling accuracy snapshots |
| `model_portfolios` | **NEW** Portfolio snapshots per archetype (immutable once deactivated) |
| `portfolio_allocations` | **NEW** Per-stock allocation weights within a portfolio snapshot |
| `portfolio_performance` | **NEW** Daily performance tracking (return, alpha, Sharpe, drawdown) |

### Performance Columns Added
- `trade_recommendations`: `benchmark_1d_return`, `alpha_1d`, `benchmark_5d_return`, `alpha_5d`, `is_live`
- `user_positions`: `benchmark_return_pct`, `alpha_pct`

## Database Compatibility
- **Boolean handling**: PostgreSQL uses `true/false`, SQLite uses `1/0`
- **Missing tables**: API returns empty array `[]` instead of 500 error
- **DISTINCT ON**: PostgreSQL-specific syntax for latest records per symbol (used in `/api/prices` and `/api/sentiment`)
- **Prices query**: PostgreSQL uses `DISTINCT ON`, SQLite uses `JOIN + GROUP BY MAX(date)`
- **Immutability triggers**: PostgreSQL only (prevents core prediction field mutations)
- **Materialized views**: PostgreSQL only (`mv_performance_global`); SQLite computes on-the-fly
- **FILTER clause**: PostgreSQL uses `FILTER (WHERE ...)`, SQLite uses `CASE WHEN` equivalent
- **ALTER TABLE**: Wrapped in try/except for safe column additions on both engines
- **Portfolio immutability triggers**: PostgreSQL only (prevents UPDATE/DELETE on deactivated portfolio snapshots)
- **Auto-deactivation**: PostgreSQL trigger deactivates previous active portfolio of same type on new insert

## Notes
- EGX stocks use `.CA` suffix (e.g., `COMI.CA`)
- Language preference stored in localStorage
- Dark mode preference stored in localStorage (key: `theme`)
- Server runs on port 3000 locally
- Production uses Render's DATABASE_URL for PostgreSQL
- Dashboard auto-refreshes data on language switch
- Prediction horizon: 1 day (changed from 7 days for faster evaluation)

\n\n## Mar 14, 2026 — UI/Deploy Fixes\n\n## Mar 14, 2026 — RAG Assistant Update\n- /api/rag/chat now pulls from all RAG sources: market reports, ETF documents, embedded news/event intel chunks.\n- Added semantic matching against 
ews_rag_chunks and included custom news sources in context when available.\n- Updated EGX knowledge block to list all internal data sources used by the assistant.\n\n- **Render boot crash**: fixed a duplicate catch block in web-ui/routes/performance.js that caused SyntaxError: missing ) after argument list on startup.\n- **Header cleanup**: removed absolute positioning from header controls and user info bar to prevent overlap; tightened small-screen behavior in web-ui/public/style.css + web-ui/public/auth.css.\n- **Snapshot bar**: removed \u201cLive-Only Data\u201d pill from the global performance snapshot bar (web-ui/public/app.js, web-ui/public/style.css).\n\n## Recent Changes (Feb 2026)
- **Time Machine Short-Window No-Data Fix (Feb 18, 2026)**:
  - Increased Time Machine historical warmup window in `engines/timemachine_data.py` from 60 to 180 days so recent start dates still have enough context for indicators.
  - Relaxed strict preflight in `engines/timemachine.py` to validate in-range price availability (instead of requiring 50-row history per symbol), preventing false "insufficient data" failures.
  - Removed hard failure for low signal counts so short windows return a valid flat simulation (0 trades) instead of an error.
  - Live API verification after fix:
    - `POST /api/timemachine/simulate` with `{amount: 5000, start_date: "2026-02-17"}` -> `200 OK`, `total_return_pct=0`, `total_trades=0`
    - `POST /api/timemachine/simulate` with `{amount: 50000, start_date: "2025-11-18"}` -> `200 OK`, `total_return_pct=18.14`, `total_trades=23`
- **Time Machine Reliability Hotfixes (Feb 18, 2026)**:
  - Hardened `engines/timemachine.py` preflight validation to check usable historical coverage (>= 3 stocks with sufficient history and in-range data) instead of fragile symbol-count checks.
  - Added resilient database fallback path in `engines/timemachine_data.py` for missing Yahoo symbols:
    - PostgreSQL `prices` via `DATABASE_URL` (production/Render)
    - SQLite `stocks.db` (local fallback)
  - Result: Time Machine simulation now succeeds for affected short ranges (including `2025-11-18`) even when Yahoo has partial EGX outages.
- **Event Intelligence + Arabic Sentiment Layer (Feb 18, 2026)**:
  - Added new production package `xmore_event_intel/` with full modular architecture:
    - Source scrapers: Enterprise, Daily News Egypt, Egypt Today, Mubasher Info, and EGX disclosures (`sources/*.py`)
    - Arabic sentiment stack: preprocessor, deterministic lexicon, strict JSON-schema LLM extractor (`arabic_sentiment/*.py`)
    - Deterministic event tagging engine (`event_tagging.py`)
    - Structured earnings delta extraction (`earnings_extractor.py`)
    - Historical validation + adaptive event-weighting loop (`performance_validator.py`)
    - Unified SQLite/PostgreSQL persistence for `articles`, `structured_events`, `sentiment_scores`, `performance_metrics` (+ `event_type_weights`) (`storage.py`)
    - End-to-end orchestrator CLI (`main.py`)
  - Live test executed successfully:
    - Command: `XMORE_EVENT_MAX_ARTICLES_PER_SOURCE=3`, `XMORE_EVENT_DELAY_SECONDS=0.1`, `XMORE_EVENT_TIMEOUT_SECONDS=8`, `XMORE_EVENT_MAX_RETRIES=1`, then `python -m xmore_event_intel.main --limit 10 --log-level INFO`
    - Result: `articles_collected=6`, `articles_processed=6`, `rolling_accuracy_30=None`, `corr_1d=None`, `corr_3d=None`, `corr_5d=None`
    - Runtime observations: some sources were skipped due robots/availability constraints (Daily News Egypt, Egypt Today, EGX robots fetch instability), while pipeline remained compliant and completed.
- **Time Machine Data Reliability Upgrade (Feb 18, 2026)**:
  - Refactored `engines/timemachine_data.py` to use a multi-source fetch strategy for EGX30 history:
    - Source 1: `yfinance` batch download (primary path)
    - Source 2: direct Yahoo Finance v8/chart API fallback per-symbol via `requests`
    - Source 3: computed `^EGX30` equal-weight proxy benchmark from available EGX30 component prices
  - Added direct API parser and resilient row shaping for missing OHLC fields and null closes.
  - Added browser-like request headers and a small per-symbol delay in fallback mode to reduce Yahoo rate-limit failures.
  - Updated logging and fetch summary flow to clearly report batch coverage, fallback-recovered symbols, and proxy creation status.
  - Kept Time Machine ingestion in-memory only (no direct DB writes in this module); local `stocks.db` was updated in the working tree by runtime activity.
- **Auth + Deployment Hotfix (Feb 15, 2026)**:
  - Updated `web-ui/middleware/auth.js` startup behavior:
    - Production now auto-generates an ephemeral JWT secret if `JWT_SECRET` is missing (service can boot)
    - Logs explicit warning that sessions will be invalidated on restart until `JWT_SECRET` is configured
    - Local/dev still supports a fallback secret with warning
  - Updated `render.yaml` to include `JWT_SECRET` with `generateValue: true` for Render Blueprint provisioning
  - Deployment note: existing Render services may still require manual env var set/redeploy to apply new secret
- **Security + Reliability Hardening (Feb 14, 2026)**:
  - Enforced required `JWT_SECRET` in `web-ui/middleware/auth.js` (removed insecure default fallback)
  - Tightened CORS behavior in `web-ui/server.js` to support explicit allowlist via `CORS_ALLOWED_ORIGINS`
  - Fixed fragile SQLite placeholder conversion (`$1..$N` ? `?`) in `web-ui/routes/trades.js` and `web-ui/routes/briefing.js`
  - Added safe JSON parsing guard for trade reasons in `web-ui/routes/trades.js`
  - Reduced broad `SELECT *` usage in `web-ui/routes/performance.js` and `web-ui/server.js` consensus detail endpoint
- **Portfolio Engine Data Quality Improvements (Feb 14, 2026)**:
  - Deduplicated portfolio signal collection by symbol in `engines/portfolio_engine.py`
  - Updated `engines/generate_portfolios.py` to compute portfolio-specific daily performance snapshots using allocation-weighted returns (instead of copying global metrics)
- **Frontend Safety + UX Improvements (Feb 14, 2026)**:
  - Added HTML escaping helpers in `web-ui/public/trades.js` and `web-ui/public/watchlist.js` to reduce XSS risk from rendered dynamic values
  - Improved watchlist empty state with actionable "Add Stock" CTA
  - Added accessibility `aria-label` on watchlist remove button
  - Added lightweight loading placeholders for trades/portfolio views
- **Portfolio Engine Phase 1 (Feb 14, 2026)**:
  - Added migration `web-ui/migrations/008_model_portfolios.sql` with new tables:
    - `model_portfolios` (portfolio snapshots)
    - `portfolio_allocations` (per-stock weights)
    - `portfolio_performance` (daily performance tracking)
  - Added PostgreSQL trigger/function protections in migration:
    - Prevent UPDATE/DELETE for inactive portfolio snapshots (`is_active = FALSE`)
    - Auto-deactivate previous active portfolio of same `portfolio_type` when inserting a new active one
  - Added archetype configuration module `engines/portfolio_config.py`:
    - `CONSERVATIVE_CONFIG` (Al-Aman)
    - `BALANCED_CONFIG` (Al-Mizan)
    - `AGGRESSIVE_CONFIG` (Al-Numu)
  - Added signal-to-allocation engine `engines/portfolio_engine.py` with 5-step pipeline:
    - collect active signals
    - filter by archetype rules
    - score/rank
    - constrained weight allocation
    - validate/publish to portfolio tables
  - Added drawdown protection in `engines/circuit_breaker.py`:
    - Increases cash allocation when latest drawdown exceeds archetype threshold
  - Added cron orchestrator `engines/generate_portfolios.py`:
    - Rebalance cadence by archetype (30/14/7 days)
    - Runs full generation flow and writes daily `portfolio_performance` snapshots
  - Added test suite `tests/test_portfolio_engine.py`:
    - constraint enforcement
    - total allocation integrity
    - cash floor checks
    - edge cases (no signals, single signal)
  - Updated workflow `.github/workflows/scheduled-tasks.yml`:
    - Added `portfolio-generation` job
    - Runs after `daily-predictions` (`needs: daily-predictions`)
    - Executes `python engines/generate_portfolios.py`
- **Screen Briefs + Translation Coverage (Feb 12, 2026)**:
  - Added short novice-friendly "what this screen does" briefs across all major tabs in `web-ui/public/index.html`:
    - Predictions, Briefing, Trades, Portfolio, Watchlist, Consensus, Performance, Results, Prices
  - Added stable IDs for each brief line so copy can be language-switched dynamically
  - Added EN + AR translation keys in `web-ui/public/app.js`:
    - `predictionsBrief`, `briefingBrief`, `tradesBrief`, `portfolioBrief`, `watchlistBrief`, `consensusBrief`, `performanceBrief`, `resultsBrief`, `pricesBrief`
  - Updated `applyLanguage()` in `web-ui/public/app.js` to map all new brief keys to DOM on language toggle (EN/AR)
- **Results Tab UX Refresh (Feb 12, 2026)**:
  - Added a single centered Results tab heading (`resultsTitle`) for cleaner section framing
  - Reworked `/api/evaluations` rendering from one flat table to **stock-grouped cards** in `web-ui/public/app.js`
  - Each stock now has a distinct visual card (accent tone, symbol/company header) to avoid similar-looking rows
  - Kept per-agent evaluation details inside each stock card and sorted rows by **newest `target_date` first**
  - Added dedicated styles in `web-ui/public/style.css` for grouped Results layout and responsive table wrapping
- **Frontend Stability Guard (Feb 12, 2026)**:
  - Fixed critical browser stack overflow in `web-ui/public/briefing.js` caused by recursive global export (`window.loadBriefing` self-call loop)
  - Corrected export to direct binding: `window.loadBriefing = loadBriefing;`
  - Added `web-ui/scripts/check-frontend-exports.js` to fail builds on recursive `window.*` export wrappers
  - Added `npm run check` in `web-ui/package.json` to run recursion guard + `node --check` on frontend JS files
- **Institutional Dashboard UX Upgrade (Feb 12, 2026)**:
  - Added **Global Performance Snapshot Bar** under header with live-only badge, 30D alpha vs EGX30, 30D Sharpe, 30D max drawdown, 30D rolling win rate, and 100-trade progress bar
  - Refactored **Predictions tab** to be **stock-first** (consensus signal, agreement %, conviction, recent symbol accuracy) with expandable per-agent breakdown and structured "Why This Signal?" grid
  - Rebuilt **Performance tab** into institutional section flow:
    - Proof of Edge (alpha/sharpe/drawdown + upgraded equity curve)
    - Stability Metrics (30/60/90 + volatility + profit factor)
    - Agent Accountability (sortable comparison fields + mini weight visual)
    - Transparency & Integrity (immutable history table, audit modal, trade-threshold progress)
    - Since Inception summary block
  - Added **System Health badge** logic on Performance tab:
    - Stable: Sharpe > 1, positive alpha, drawdown controlled
    - Watch: borderline metrics
    - Degraded: weakening profile
  - Upgraded **equity curve chart** (canvas) with:
    - Hover tooltip (Xmore return, EGX30 return, alpha)
    - Toggle benchmark line on/off
    - Toggle drawdown shading on/off
    - Mobile-responsive interaction model
  - Expanded `/api/performance-v2/summary` output to include:
    - Global: `sharpe_ratio`, `max_drawdown`, `volatility`, `profit_factor`
    - Rolling: `30d`, `60d`, `90d` windows with risk and stability fields
  - Preserved bilingual support (EN/AR), RTL/LTR consistency, dark/light mode behavior, and responsive layout
- **Bug Fixes (Critical)**:
  - Fixed `init-db.js` missing `sentiment_scores` table creation (sync with `database.py`)
  - Fixed `agents/agent_ma.py` off-by-one error and "fresh crossover" logic flaw
  - Fixed `lxml` dependency for EGX live scraper
  - Added `finnhub-python` dependency for sentiment analysis
- **TDZ Fix**: `applyTheme()` crashed accessing `const TRANSLATIONS` before init; wrapped in try/catch
- **Predictions Workflow Fix**: Removed broken `needs: daily-collection` dependency that prevented `daily-predictions` from ever running on schedule
- **Dashboard Load Performance**: Parallelized API calls, eliminated duplicate fetch, optimized SQL, skeleton loader
- **Cache-Busting**: Static assets use `?v=` query params; `window.onerror` shows JS errors on-page
- **Dark Mode Toggle**: Added `.theme-btn` with sun/moon icons, CSS custom properties, system preference detection
- **Daily Predictions**: 1-day horizon for faster evaluation turnaround
- **GitHub Actions Upgraded**: All jobs now use `actions/checkout@v4`

## Phase 1 Upgrade (Feb 2026)
- **EGX Live Scraper**: `data/egx_live_scraper.py` scrapes live EGX feed with yfinance fallback
- **TA-Lib Integration**: `features.py` rewritten with 40+ indicators, pure Python fallback
- **VADER Sentiment**: Dual-engine (VADER fast + FinBERT deep) with auto mode and source weighting
- **Performance Dashboard**: Tabbed UI, per-agent/per-stock stats, monthly accuracy chart (canvas)
- **TradingView Widgets**: Ticker tape + lazy-loaded mini charts, locale-aware
- **Compliance**: Signal terminology â†’ Bullish/Bearish, bilingual disclaimers, `TERMS.md`
- **Consensus Agent**: `agents/agent_consensus.py` â€” accuracy-weighted voting across all agents
- **Dependencies Added**: `lxml`, `vaderSentiment`, `quantstats`, `TA-Lib`

## Phase 3 Upgrade: Performance System (Feb 12, 2026)
- **Performance Evaluation Engine** (`engines/evaluate_performance.py`): Resolves 1d/5d outcomes, calculates EGX30 benchmark returns + alpha, updates agent accuracy snapshots, refreshes materialized views
- **Performance Metrics Calculator** (`engines/performance_metrics.py`): Sharpe ratio, Sortino ratio, max drawdown, profit factor, rolling windows, equity curve data, agent comparison
- **Investor-Grade API** (`web-ui/routes/performance.js`): 7 public endpoints under `/api/performance-v2/` â€” summary, by-agent, by-stock, equity-curve, predictions/open, predictions/history, audit
- **Performance Dashboard** (`web-ui/public/performance-dashboard.js` + `.css`): Premium dark/light dashboard with key metrics grid, canvas equity curve chart, agent accuracy table, stock chips, prediction history pagination, audit modal, integrity section, bilingual support
- **Database Schema** (`007_performance_benchmark.sql`, `database.py`): Immutability triggers, audit trail table, benchmark columns, agent performance table, materialized view
- **Pipeline Integration** (`run_agents.py`): Performance evaluation added as Step 8 after briefing generation
- **Briefing Track Record** (`engines/briefing_generator.py`): Daily briefing now includes 30-day rolling performance snippet
- **Data Integrity**: Core predictions immutable (PostgreSQL triggers), all outcome changes audited, live-only metrics, 100-trade minimum threshold
- **See**: `docs/PERFORMANCE_SYSTEM.md` for full architecture documentation






## xmore_data Verification + Runtime Hardening (Feb 15, 2026)
- Completed an end-to-end verification of the EGX data ingestion layer implementation under `xmore_data/`.
- Closed requirement gaps found during audit:
  - Added required public API wrappers in `xmore_data/data_manager.py`:
    - `fetch_egx_data(...)`
    - `fetch_multiple_symbols(...)`
    - `get_egx30_index(...)`
  - Exported these functions in `xmore_data/__init__.py` for package-level usage.
  - Hardened schema standardization in `xmore_data/utils.py`:
    - Canonical provider-column mapping (including Alpha Vantage keys like `1. open`, `2. high`, etc.)
    - Enforced exact final output schema and order:
      `Date | Open | High | Low | Close | Adj Close | Volume`
  - Fixed Alpha Vantage normalization flow in `xmore_data/providers/alpha_vantage_provider.py` to rely on canonical validation mapping and preserve adjusted close when present.
  - Updated CLI import behavior in `xmore_data/main.py` to support both:
    - `python -m xmore_data.main ...`
    - `python xmore_data/main.py ...`
  - Extended date parsing in `xmore_data/utils.py` to accept `today` and `yesterday` tokens (matching CLI examples).
  - Ensured runtime directory readiness on import in `xmore_data/config.py` by creating:
    - `Config.CACHE_DIR`
    - `Config.LOG_FILE.parent`
- Runtime checks executed:
  - `python -m py_compile xmore_data/config.py xmore_data/utils.py xmore_data/data_manager.py xmore_data/providers/alpha_vantage_provider.py xmore_data/main.py xmore_data/__init__.py` -> passed.
  - `python -m pytest xmore_data/test_data_manager.py -v -m "not slow"` -> passed (`23 passed, 1 deselected`).

## RSS + EGX Web Adapter Live Test (Feb 15, 2026)
- Added optional EGX web news adapter behind feature flag:
  - `config.py` -> `EGX_CONFIG['use_egx_web_scraper'] = False` (default)
  - `rss_news_collector.py` -> `fetch_egx_web_news()` with anti-bot rejection detection and graceful fallback
  - Runtime toggle via env: `USE_EGX_WEB_SCRAPER=true`
- Added Mubasher feed as high-priority EGX source:
  - `http://feeds.mubasher.info/en/EGX/news`
  - Priority note added in `rss_news_collector.py`
- Added daily EGX snapshot automation:
  - `xmore_data/daily_snapshot_job.py` (EGXPY-first with provider fallback, per-symbol exports + manifest)
  - `.github/workflows/scheduled-tasks.yml` new cron `0 14 * * 0-4` and artifact upload
  - `xmore_data/data_manager.py` source tracking (`cache` / provider name)
- Live test executed with EGX web adapter enabled:
  - Command: `USE_EGX_WEB_SCRAPER=true python -c "from rss_news_collector import collect_rss_news; ..."`
  - Result:
    - `feeds_processed`: 6
    - `articles_fetched`: 160
    - `articles_matched`: 11
    - `articles_saved`: 44
    - `egx_web_processed`: 1
    - `egx_web_articles_fetched`: 0
    - `egx_web_articles_saved`: 0
    - `errors`: 0
  - Interpretation: RSS path is working in live mode; EGX website adapter remained non-blocking and returned 0 candidates (no runtime failure).
- Environment note:
  - Installed missing dependency for live run: `feedparser` (global python env).

## Admin Dashboard + Market Intelligence Update (Feb 16, 2026)
- Added secure admin interface at `/admin` protected by `ADMIN_SECRET` (separate from standard JWT auth).
- Added shared middleware: `web-ui/middleware/admin.js`.
- Protected admin assets/routes in `web-ui/server.js`:
  - `/admin`, `/admin.html`, `/admin.js`
  - `/api/admin/*`
- Added admin API module: `web-ui/routes/admin.js`:
  - `GET /api/admin/system-health`
  - `GET /api/admin/reports`
  - `POST /api/admin/reports/upload` (multer PDF upload)
- Added PDF ingestion engine: `engines/ingest_report.py` (pdfplumber text extraction, EN/AR detection, JSON output for Node persistence).
- Added DB migration: `web-ui/migrations/009_market_reports.sql` for `market_reports` table.
- Added startup DB init coverage in `web-ui/init-db.js` to create `market_reports` on Render boot.
- Added admin frontend:
  - `web-ui/public/admin.html`
  - `web-ui/public/admin.js`
  - Admin styles in `web-ui/public/style.css`
- Added deployment env entry in `render.yaml`: `ADMIN_SECRET` with `generateValue: true`.
- Operations note:
  - Existing Render services may still require manual `ADMIN_SECRET` set + redeploy.
  - If an admin secret is exposed in chat/logs, rotate it immediately.

## News Intelligence Layer Rollout (Feb 16, 2026)
- Added new modular package: `xmore_news/` with production-oriented ingestion pipeline:
  - `xmore_news/config.py`
  - `xmore_news/sources/reuters_scraper.py`
  - `xmore_news/sources/alarabiya_scraper.py`
  - `xmore_news/sources/egypt_local_scraper.py`
  - `xmore_news/parser.py`
  - `xmore_news/sentiment_preprocessor.py`
  - `xmore_news/storage.py`
  - `xmore_news/scheduler.py`
  - `xmore_news/main.py`
- Implemented core functions and architecture requirements:
  - `fetch_reuters_news()` / `fetch_alarabiya_news()` / `fetch_egypt_news()`
  - `normalize_article(...)`
  - `extract_company_mentions(...)`
  - `save_articles_to_db(...)`
  - `prepare_for_sentiment(...)`
- Storage schema added in SQLite (`news_articles`) with URL + URL-hash dedupe and processing flags.
- Added compliance controls:
  - robots.txt checks
  - per-request delay
  - retry with exponential backoff
  - source-level failure isolation
- Added scheduler support via APScheduler with configurable 30-minute interval.
- Added source feed hardening:
  - Reuters + Al Arabiya source-specific Google News RSS fallback endpoints in addition to primary RSS/listing URLs.
- Test compatibility fix:
  - Updated `xmore_data/test_data_manager.py` datetime assertion to tolerate precision differences (`datetime64[ns]` vs `datetime64[us]`) on newer Python/pandas builds.
- Validation snapshot:
  - `npm run check` (web-ui) passed.
  - `tests/test_portfolio_engine.py` passed.
  - `xmore_data/test_data_manager.py -m "not slow"` passed after dtype fix (`23 passed, 1 deselected`).
  - Live `xmore_news` run inserted 160 records to test DB from accessible sources.
- Runtime note:
  - Reuters/Al Arabiya may still return zero in restricted environments due to robots/403/network policy; pipeline remains compliant and continues with available sources.

## Sentiment Intelligence Layer Rollout (Feb 16, 2026)
- Added new financial-grade package: `xmore_sentiment/`:
  - `schemas.py` (Pydantic models for strict structured extraction + scoring outputs)
  - `extractor.py` (LLM JSON-schema constrained fact extraction only; no free-text sentiment)
  - `rule_engine.py` (deterministic financial event scoring)
  - `confidence.py` (weighted confidence modeling)
  - `validator.py` (keyword polarity check + disagreement handling + historical metrics)
  - `scorer.py` (orchestration for raw score, confidence, final sentiment)
  - `storage.py` (SQLite/PostgreSQL tables: `articles`, `extracted_facts`, `sentiment_scores`, `validation_metrics`)
  - `main.py` (CLI pipeline runner)
- Hallucination controls implemented:
  - LLM restricted to schema-constrained fact extraction JSON
  - invalid JSON discarded and logged
  - no direct LLM sentiment classification allowed
- Rule engine + confidence features:
  - deterministic mapping for earnings/guidance/debt/macro/regulatory signals
  - macro-only content down-weighting when not company-specific
  - confidence combines certainty, entity strength, quantitative extraction, and rule/keyword agreement
- Dual validation + self-correction:
  - dictionary polarity cross-check
  - disagreement threshold marks uncertain records and applies penalty
  - rolling performance metrics and auto-adjusting weight multiplier after sufficient sample size
- Risk controls in code:
  - sentiment can only adjust signal confidence/position sizing
  - sentiment does not independently trigger trades
- Dependency update:
  - added `pydantic>=2.8.0` to `requirements.txt`
- Sanity checks:
  - module compile checks passed
  - CLI help works
  - dry run with `--limit 0` completed successfully

## Trades/Portfolio Empty-State Hotfix (Feb 17, 2026)
- Fixed critical pipeline bug in `run_agents.py` where multiple functions used `database.get_connection()` despite importing `get_connection` directly.
  - Result: removed `name 'database' is not defined` failures that blocked trade recommendation and briefing generation during daily pipeline runs.
- Added watchlist seeding in `generate_daily_trade_recommendations(...)`:
  - Active users with no `user_watchlist` rows now receive a baseline set of 10 EGX30 symbols.
  - Recommendation generation then runs for all active users with watchlists.
- Relaxed trades API behavior in `web-ui/routes/trades.js`:
  - `GET /api/trades/today` now falls back to the userâ€™s latest available recommendation date when today has no rows.
  - API response summary now includes `date` (effective date used) and `fallback_used` (boolean).
- Verified historical GitHub Actions logs contained the exact failing messages before fix:
  - `Error generating trade recommendations: name 'database' is not defined`
  - `Error generating briefing: name 'database' is not defined`
## Admin Route Bootstrap Fix (Feb 17, 2026)
- Root cause identified for {"error":"Admin access denied"} on direct /admin visits:
  - web-ui/server.js protected /admin, /admin.html, and /admin.js with requireAdminSecret, preventing initial page load when no admin secret cookie/header existed yet.
- Implemented fix:
  - Removed pre-auth middleware for admin static routes in web-ui/server.js.
  - Kept /api/admin/* protected via router.use(requireAdminSecret) in web-ui/routes/admin.js.
- Result:
  - Admin page can now load first, allowing secret entry in UI.
  - Admin APIs remain protected and still require valid ADMIN_SECRET.


## Track Record UX Refresh (Mar 16, 2026)
- web-ui/public/track-record.css: mobile cleanup at <=640px, tighter spacing, responsive header controls, feed wrapping, sector rows stacked, tracker panel becomes bottom sheet
- web-ui/public/track-record.html: agent + top-stocks tables flagged for mobile card layout
- web-ui/public/track-record.js: table cells emit localized data-label values; log table labels localized; language toggle re-renders log to update labels


## UI/UX Unification & Mobile Readability (Mar 16, 2026)
- Added shared UI tokens + reusable topbar in `web-ui/public/base.css` and applied across public pages.
- Unified language persistence using `localStorage('lang')` on Track Record, Pro, and Session.
- Fixed mojibake/encoding in public HTML/JS (UTF-8 normalized).
- Standardized navigation links across pages (Home, Track Record, Pro, Session, Docs).
- Added mobile card layout for dense tables on dashboard, track record, session, comparisons, and ETF tables.
- Localized card/table labels for comparisons, multi-horizon accuracy, and ETF cards/tables.
- Increased base font size to 14px on main dashboard/Track Record/Pro/Session; reduced micro-label all-caps.
- Added global reduced-motion handling in `base.css`.


## Track Record Copy Tweak (Mar 16, 2026)
- `web-ui/public/track-record.html`: header badge shortened to ?Live pre-market signals?.
## Mar 18, 2026 - Docs Arabic RTL Sync
- Updated web-ui/public/docs.html language initialization to honor Arabic preference from localStorage('lang').
- Added ?lang=ar/?lang=en query override on /docs.
- Docs page now auto-applies dir='rtl' + right-aligned layout in Arabic without requiring a separate docs-only toggle state.
- Docs language toggle now syncs both docs-lang and global lang in localStorage.

## Mar 19, 2026 - Live Validation + Deploy
- Live smoke test passed against https://xmore-project.onrender.com after pushing main.
- Verified HTTP 200 for: /, /docs, /landing, /pro, /session, /track-record, /admin.
- Verified HTTP 200 for APIs: /api/consensus, /api/intelligence/changes, /api/intelligence/quality, /api/performance-v2/summary.
- Verified /api/consensus now returns calibrated_confidence, expected_edge_pct, and ranking_score.
- Verified /api/intelligence/changes returns signal, forecast, and macro change groups.
- Verified /api/intelligence/quality returns overall_status, freshness, and drift.
- Verified /api/rag/chat returns retrieval_meta.resolved_entities and sources on a live request.
- Validation also found and fixed pre-existing syntax errors in web-ui/public/performance-dashboard.js; npm run check now passes locally.

## Mar 19, 2026 - Financial Audit Follow-Through
- `run_agents.py`
  - Kelly sizing now runs on BUY recommendations before execution realism via `apply_kelly_sizing(...)`.
  - stored recommendation rows now persist execution/sizing fields when schema columns exist:
    - `realistic_fill_price`
    - `position_value_egp`
    - `round_trip_cost_egp`
    - `edge_ratio`
    - `split_required`
    - `realistic_stop_price`
    - `execution_approved`
    - `position_size_pct`
    - `volatility_position_pct`
    - `kelly_position_pct`
    - `shares_requested`
    - `shares_expected`
    - `position_sizing_mode`
  - trade recommendation column introspection cache now avoids permanently caching an empty result set.
- `engines/execution_agent.py`
  - live sizing now blends volatility-based sizing with upstream Kelly sizing using `position_sizing_mode` values:
    - `volatility_only`
    - `kelly_overlay`
- `engines/kelly_allocator.py`
  - allocator now uses resolved live BUY performance rows as the learning basis.
  - symbol-specific stats fall back to global BUY stats when sample size is thin.
  - allocation flooring was tightened so post-floor normalization does not exceed `MAX_TOTAL_EXPOSURE`.
- Backtest realism upgraded:
  - new helper `engines/backtest_friction.py`
  - `engines/backtest.py` and `engines/walk_forward_backtest.py` now use slippage-aware, fill-aware, transaction-cost-aware directional returns instead of only flat cost drag.
  - stored per-trade friction fields include:
    - `gross_direction_return_pct`
    - `net_direction_return_pct`
    - `fill_ratio`
    - `slippage_drag_pct`
    - `transaction_cost_pct`
- Public performance publication standard updated:
  - `web-ui/routes/performance.js` now reports net-of-transaction-cost metrics as primary and keeps gross metrics as secondary context.
  - `web-ui/routes/track-record.js` now reports summary, equity curve, top-stocks, sector, and regime outputs on a net-first basis with gross secondary fields.
  - `web-ui/public/track-record.js` copy now explicitly describes Sharpe, alpha, profit factor, volatility, and return metrics as net-of-cost metrics.
- Schema/bootstrap coverage added:
  - `database.py`
  - `web-ui/init-db.js`
  - `migrations/add_execution_realism_columns.sql`
  - all now include execution realism and Kelly sizing columns listed above.
- Dashboard audit widget compatibility fixed in `dashboard.py`:
  - execution filter stats now read `total`, `approved`, `blocked_by_edge`, and `split_required`
  - profitability display handles both fraction and percent style inputs safely.
- Verification run completed locally:
  - `python -m py_compile run_agents.py engines/execution_agent.py engines/kelly_allocator.py engines/portfolio_rebalancer.py engines/backtest_friction.py engines/backtest.py engines/walk_forward_backtest.py database.py dashboard.py`
  - `node --check web-ui/routes/performance.js`
  - `node --check web-ui/routes/track-record.js`
  - `node --check web-ui/public/track-record.js`
  - `node --check web-ui/init-db.js`
  - `python -m pytest tests/test_execution_realism.py -q` -> `12 passed`
- KSA deployment URL split corrected:
  - `https://xmore-ksa.onrender.com/` is now the canonical KSA dashboard route
  - `https://xmore-ksa.onrender.com/track-record` is now the canonical KSA track-record route
  - KSA market switcher now points the EGX button to `https://xmore-project.onrender.com/`
  - legacy `/ksa` and `/ksa/track-record` paths remain only as redirects for compatibility
  - updated `web-ui/server.js`, `web-ui/public/ksa-dashboard.html`, and `web-ui/public/ksa-track-record.html`
- KSA track-record now uses the full public track-record page stack instead of the slim KSA-only variant:
  - `/track-record` now serves `web-ui/public/track-record.html`
  - `web-ui/routes/track-record.js` was hardened for KSA-only data (`market_id = 'KSA'`)
  - EGX joins/labels/risk-free assumptions were replaced with KSA/TASI equivalents
  - agent, prediction log, sector, regime, and distribution endpoints now read KSA-compatible columns
- Remaining audit gap:
  - backtests are now materially friction-aware, but they still do not simulate the full stop-loss lifecycle with explicit gap-through-stop execution behavior end-to-end.
