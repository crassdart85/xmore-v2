# Xmore KSA Plan

## Objective

Convert Xmore from an EGX-first product into a KSA-first Tadawul product without breaking the current application surface while the broader backend migration is still in progress.

## Completed KSA Changes

### 1. User-facing market conversion

The active web experience was shifted from Egypt and Tadawul wording to Saudi Exchange and Tadawul wording across the main public surfaces.

Files already converted in the KSA version include:

- web-ui/public/index.html
- web-ui/public/app.js
- web-ui/public/landing.html
- web-ui/public/docs.html
- web-ui/public/assistant-widget.js
- web-ui/public/performance-dashboard.js
- web-ui/public/track-record.html
- web-ui/public/track-record.js
- web-ui/public/pro.html
- web-ui/public/pro.js
- web-ui/public/session.html
- web-ui/server.js
- agents/gemini_agent.py
- ana_lyze/prompts.py

Key outcomes:

- visible market copy now references Tadawul, Saudi market, TASI, and SAR
- TradingView widgets on the main dashboard and Pro page now use Saudi tickers
- /pro and /session are restored as real pages instead of redirects
- Pro and Session pages filter out non-Saudi symbols so the KSA-branded experience does not leak Tadawul rows

### 2. KSA-first forecast and symbol handling

Forecast-related logic was changed from TASI assumptions to a Tadawul-first universe.

Files:

- web-ui/services/marketUniverse.js
- web-ui/services/forecastEngine.js
- web-ui/routes/timemachine.js
- web-ui/routes/portfolioForecasts.js

Key outcomes:

- manual forecast symbols now resolve with KSA-first logic
- auto forecast mode scans a Tadawul universe instead of TASI
- forecast display symbols normalize .SR cleanly
- portfolio forecasts now run against resolved Saudi symbols

### 3. Tadawul stock metadata layer

The shared reference table still has the historical name egx30_stocks, but it now carries Tadawul metadata for the KSA version.

Files:

- config/ksa_universe.py
- database.py
- web-ui/routes/stocks.js

Key outcomes:

- added a real KSA universe file with 41 Saudi symbols and metadata
- database initialization now seeds the Saudi reference rows into egx30_stocks
- the public stocks endpoint prefers .SR rows and falls back only if Saudi rows are unavailable

### 4. Pipeline defaults moved to KSA

The Python runtime defaults were shifted to Saudi symbols and Riyadh market hours while preserving legacy variable names for compatibility.

Files:

- config.py
- config/execution_config.py

Key outcomes:

- default tracked stock universe now resolves to Tadawul symbols
- EGX_STOCKS remains as a compatibility alias to the KSA list for older modules
- EGX_CONFIG remains as a compatibility alias to KSA market configuration
- collection time now aligns with Tadawul close instead of Cairo close
- regime ticker default is now ^TASI in the execution config

### 5. Backfill path for Tadawul price history

The historical backfill path now supports a real KSA universe and was hardened for PostgreSQL.

Files:

- backfill_history.py

Key outcomes:

- schema creation now runs automatically before backfill
- KSA universe loading now works because config/ksa_universe.py exists
- PostgreSQL count handling was fixed for RealDict rows
- existing row counts are now fetched in batches instead of one connection per symbol
- PostgreSQL inserts are now bulk upserts instead of row-by-row writes
- NaN Yahoo volume values are normalized safely instead of crashing inserts

## Live Migration Results

The following live validation was completed against the Render PostgreSQL database used by the web application.

### Tadawul metadata backfill

- Saudi metadata rows present in egx30_stocks: 41

### Tadawul historical price backfill

- Saudi price rows present in prices where symbol ends with .SR: 50,503
- distinct Saudi symbols present in prices: 41

These rows were inserted using bulk PostgreSQL upserts from Yahoo Finance history.

## Wider Live Tests

Local server code was started against the live PostgreSQL database and the following end-to-end checks passed.

### API validation

- GET /api/stocks
  - returned 41 Saudi stocks
  - first symbols returned were Saudi .SR symbols

- POST /api/timemachine/forecast with symbol 2222
  - resolved to 2222.SR
  - returned a successful forecast response

- POST /api/timemachine/forecast with symbol auto
  - returned a successful forecast response
  - selected a Saudi symbol from the Tadawul universe

## Current State of the KSA Version

The KSA version is now materially different from the original Tadawul build in four important ways:

1. the default symbol universe is Saudi
2. the live reference metadata includes Saudi stocks
3. the live price store now contains Saudi historical price coverage
4. the main forecast and market pages can operate on Saudi symbols end to end

## Remaining Gaps

Most gaps identified during the original migration have now been resolved (April 2026 P3+P4+P5 remediation). Completed items are marked below.

1. ~~route-layer cleanup for remaining egx30_stocks assumptions~~ **DONE (April 2026)**
   - stocks.js, trades.js, watchlist.js, rag.js now use `STOCK_TABLE` constant
   - performance.js and screening.js already used STOCK_TABLE / were correct

2. data-model cleanup for legacy Tadawul naming such as:
   - `alpha_vs_egx30`, `egx30_return_pct`, `round_trip_cost_egp` — **retained as legacy DB column names** (require schema migration to rename; functional as-is since they store KSA data)

3. ~~benchmark data source work for TASI index history~~ **DONE (April 2026)**
   - Regime proxy now uses `TASI.INDX`, `^TASI`, `2222.SR`
   - Benchmark evaluation uses `TASI_BENCHMARK_SYMBOLS`

4. ~~sentiment and research layers still contain some EGX-specific symbol handling~~ **DONE (April 2026)**
   - `sentiment_gemini.py` now uses `KSA_TOP50` from `config.ksa_universe`
   - `rss_news_collector.py` replaced 13 Egypt feeds with 9 Saudi/GCC feeds
   - `custom_source_fetcher.py` uses Tadawul keywords and `.SR` fallbacks

5. ~~non-web pipeline modules still contain legacy EGX-specific datasets~~ **DONE (April 2026)**
   - `collect_data.py`: `collect_ksa_data()`, `_fetch_usdsar_rate()`, `MACRO_USDSAR`
   - `run_agents.py`: TASI regime proxy
   - `agent_ml.py`, `backtest.py`, `features.py`: `MACRO_USDSAR` / `usdsar_*` columns
   - `backfill_history.py`: cleaned macro symbol list
   - `evaluate_performance.py`: market-scoped with `market_id` parameter
   - `config/ksa_holidays.py`: shared Saudi holiday calendar

## Known Legacy Names Retained (No Runtime Impact)

These items use legacy naming in the database schema or inactive modules. They do not affect KSA runtime behavior:

| Item | Location | Reason Kept |
|------|----------|-------------|
| `egx30_stocks` table | database.py, routes | Schema migration required; table holds KSA `.SR` rows |
| `egx30_return_pct` column | generate_portfolios.py | Migration 008 column; stores TASI benchmark data |
| `round_trip_cost_egp` column | trade_recommendations | Legacy column name; holds SAR values |
| `openbb_egx/` module | Package directory | Standalone OpenBB provider; retained as legacy module |
| `EGX_STOCKS` alias | config.py | Backward-compat alias → `KSA_STOCKS` |

## Schema Columns Auto-Applied by `database.py` `create_tables()`

| Column | Table | Purpose |
|--------|-------|---------|
| `confidence_score` | `predictions` | Consensus confidence from softmax-weighted agent agreement |
| `is_simulated` | `trade_recommendations` | Distinguishes simulated (backfill) recs from live signals; used by track-record `simFilter()` |

## Recommended Next Phase

1. ~~replace remaining egx30_stocks joins with a market-neutral reference abstraction~~ **DONE**
2. ~~migrate benchmark computation from EGX semantics to TASI semantics~~ **DONE**
3. ~~finish KSA conversion in RAG and screening routes~~ **DONE**
4. add a reliable Tadawul benchmark ingestion source for TASI and MT30
5. run a fresh deploy and post-deploy smoke test against the production app endpoints