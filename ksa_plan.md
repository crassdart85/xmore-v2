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

The migration is not complete across the full repo. Important remaining work includes:

1. route-layer cleanup for remaining egx30_stocks assumptions in:
   - web-ui/routes/briefing.js
   - web-ui/routes/watchlist.js
   - web-ui/routes/performance.js
   - web-ui/routes/track-record.js
   - web-ui/routes/rag.js
   - web-ui/routes/screening.js

2. data-model cleanup for legacy Tadawul naming such as:
   - alpha_vs_egx30
   - egx30_return_pct
   - EGX-named benchmark fields and comments

3. benchmark data source work for TASI index history
   - Yahoo Finance did not provide a working ^TASI or TASI.SR index series in this environment
   - index-level Tadawul benchmark backfill still needs a reliable source

4. sentiment and research layers still contain some EGX-specific symbol handling and prompt/reference content in secondary paths

5. non-web pipeline modules still contain legacy EGX-specific datasets and naming that should be reviewed before calling the migration complete

## Recommended Next Phase

1. replace remaining egx30_stocks joins with a market-neutral reference abstraction
2. migrate benchmark computation from TASI semantics to TASI semantics across performance and track-record routes
3. finish KSA conversion in RAG and screening routes
4. add a reliable Tadawul benchmark ingestion source for TASI and MT30
5. run a fresh deploy and post-deploy smoke test against the production app endpoints