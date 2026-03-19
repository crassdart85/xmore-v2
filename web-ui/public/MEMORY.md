# Xmore Project Memory

## Project Overview
Stock trading prediction system with web dashboard. Uses multiple AI agents to predict stock movements.

**Last Updated**: February 12, 2026

> **Note**: The primary MEMORY.md is at the project root (`/MEMORY.md`). This file is kept for quick reference within the web-ui directory.

## Deployment Architecture
- **Render.com** - Hosts web dashboard + PostgreSQL database
- **GitHub Actions** - Runs scheduled automation tasks
- **GitHub** - Source code repository

## Key Files (Web UI)
- `public/app.js` - Frontend JavaScript (tabs, TradingView, bilingual)
- `public/performance-dashboard.js` - **NEW** Performance dashboard UI (canvas chart, agent table, audit modal)
- `public/performance-dashboard.css` - **NEW** Performance dashboard styling (dark/light, RTL, responsive)
- `public/trades.js` - Frontend logic for trades dashboard
- `public/style.css` - Dashboard styling with tabs, RTL, responsive
- `public/index.html` - Dashboard HTML (tabs, TradingView ticker, performance section)
- `server.js` - Express API server (SQLite local, PostgreSQL production)
- `routes/trades.js` - API routes for trades and portfolio
- `routes/performance.js` - **NEW** Investor-grade performance API routes (`/api/performance-v2/*`)
- `migrations/007_performance_benchmark.sql` - **NEW** Performance schema migration

## Track Record UX (Mar 16, 2026)
- track-record.css: mobile layout cleanup at <=640px; tracker panel becomes bottom sheet
- track-record.html: agent + top-stocks tables set for mobile card layout
- track-record.js: localized data-labels for log + table cards; language toggle refreshes log

## UI/UX Unification (Mar 16, 2026)
- Added shared tokens/topbar in `base.css`; applied across public pages.
- Unified language persistence (`localStorage('lang')`).
- UTF-8 normalization to fix encoding artifacts.
- Added nav links and Session link in main header.
- Mobile card layouts for dense tables, including comparisons and ETFs.
- Localized comparison/ETF labels and standardized base font size to 14px.

## Track Record Copy (Mar 16, 2026)
- `track-record.html`: header badge shortened to ?Live pre-market signals?.

## Adaptive Weighting + Change Intelligence (Mar 19, 2026)
- `../server.js`
  - `/api/consensus` and `/api/consensus/:symbol` now expose calibrated confidence, expected edge, ranking score, and stored calibration metadata.
  - added `/api/intelligence/changes` for latest-vs-previous change detection across:
    - consensus signal shifts
    - authenticated portfolio forecast deltas
    - macro moves from FX and market regime history
  - added `/api/intelligence/quality` for freshness checks and agent drift monitoring.
- `../routes/rag.js`
  - assistant retrieval now resolves bilingual entities from `egx30_stocks`, `instrument`, and `instrument_alias`.
  - symbol/entity-specific news and structured chunks are prioritized ahead of generic retrieval.
  - `retrieval_meta` includes resolved entities.
- `app.js`
  - consensus cards display calibrated confidence and expected edge.
  - added dashboard intelligence pulse rendering for:
    - What Changed Today
    - Freshness & Drift
- `index.html` and `style.css`
  - added a new dashboard section below the snapshot bar for change detection and quality monitoring.

## Environment Variables (Secrets)
- `DATABASE_URL` - PostgreSQL connection string (Render)
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
- **Performance Evaluation Engine** - Resolves outcomes, calculates alpha vs EGX30 benchmark, agent accuracy (Phase 3)

## API Endpoints
- `/api/predictions` - Latest predictions from all agents (includes disclaimer)
- `/api/performance` - Agent accuracy statistics (legacy)
- `/api/performance/detailed` - Full breakdown (per-agent, per-stock, monthly trend) (legacy)
- `/api/performance-v2/summary` - **NEW** Investor-grade overall performance + rolling metrics
- `/api/performance-v2/by-agent` - **NEW** Per-agent accuracy comparison
- `/api/performance-v2/by-stock?days=N` - **NEW** Per-stock performance breakdown
- `/api/performance-v2/equity-curve?days=N` - **NEW** Cumulative return series (Xmore vs EGX30)
- `/api/performance-v2/predictions/open` - **NEW** Currently open predictions
- `/api/performance-v2/predictions/history?page=N&limit=N` - **NEW** Auditable prediction history
- `/api/performance-v2/audit?limit=N` - **NEW** Prediction modification audit trail
- `/api/evaluations` - Prediction results (predicted vs actual)
- `/api/sentiment` - Latest sentiment scores per stock
- `/api/prices` - Latest stock prices
- `/api/trades/today` - Today's active trade recommendations
- `/api/trades/history` - Historical trade recommendations
- `/api/portfolio` - User portfolio (open positions, performance stats)
- `/api/stats` - System statistics

## Common Tasks
**Local Development:**
- Start server: `cd web-ui && npm install && node server.js`
- Run agents: `python run_agents.py` (includes performance evaluation as Step 8)
- Evaluate performance: `python -c "from engines.evaluate_performance import run_evaluation; run_evaluation()"`
- Collect data: `python collect_data.py`
- Collect sentiment: `python sentiment.py` (requires FINNHUB_API_KEY)

## Database Compatibility
- **Boolean handling**: PostgreSQL uses `true/false`, SQLite uses `1/0`
- **Missing tables**: API returns empty array `[]` instead of 500 error
- **DISTINCT ON**: PostgreSQL-specific syntax for latest records per symbol
- **Immutability triggers**: PostgreSQL only (prevents core prediction field mutations)
- **Materialized views**: PostgreSQL only (`mv_performance_global`); SQLite computes on-the-fly

## Notes
- EGX stocks use `.CA` suffix (e.g., `COMI.CA`)
- Language preference stored in localStorage
- Dark mode preference stored in localStorage (key: `theme`)
- Server runs on port 3000 locally
- Production uses Render's DATABASE_URL for PostgreSQL
- Dashboard auto-refreshes data on language switch
- Prediction horizon: 1 day (changed from 7 days for faster evaluation)
- See root `MEMORY.md` and `docs/PERFORMANCE_SYSTEM.md` for full details

## Mar 19, 2026 - Live Validation + Deploy
- Live smoke test passed against https://xmore-project.onrender.com after pushing main.
- Verified HTTP 200 for: /, /docs, /landing, /pro, /session, /track-record, /admin.
- Verified HTTP 200 for APIs: /api/consensus, /api/intelligence/changes, /api/intelligence/quality, /api/performance-v2/summary.
- Verified /api/consensus now returns calibrated_confidence, expected_edge_pct, and ranking_score.
- Verified /api/intelligence/changes returns signal, forecast, and macro change groups.
- Verified /api/intelligence/quality returns overall_status, freshness, and drift.
- Verified /api/rag/chat returns retrieval_meta.resolved_entities and sources on a live request.
- Validation also found and fixed pre-existing syntax errors in web-ui/public/performance-dashboard.js; npm run check now passes locally.
