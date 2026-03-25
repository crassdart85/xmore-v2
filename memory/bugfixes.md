# Xmore Bug Fix Log

## Mar 25, 2026

### KSA production crash from callback-only DB adapter
- **Error**:
  - Render logs showed:
    - `TypeError: Cannot read properties of undefined (reading 'length')`
    - followed by `TypeError: callback is not a function` in `web-ui/server.js`
- **Cause**:
  - the shared DB adapter in `web-ui/server.js` only supported callback-style calls
  - some KSA routes and services used promise-style `await db.all(...)` / `await db.get(...)`
  - under PostgreSQL, that caused the adapter to call an undefined callback and crash the process
- **Fix**:
  - upgraded the DB adapter to support both callback and promise usage in PostgreSQL and SQLite modes
  - this also covers KSA routes that still use direct promise-style access, such as DCF handlers
- **Pattern**:
  - in this repo, route code already mixes callback and async/await styles; the adapter must tolerate both instead of assuming one convention

### KSA init-db warnings from missing `market_id` on shared tables
- **Error**:
  - init logs showed repeated warnings like `DDL skipped: column "market_id" does not exist`
- **Cause**:
  - some shared tables can already exist from older schema versions without `market_id`
  - KSA startup then tried to create indexes on `market_id`
- **Fix**:
  - `web-ui/init-db-ksa.js` now runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'` before creating those indexes
- **Pattern**:
  - when a branch overlays market partitioning onto shared tables, add idempotent backfill migrations before creating market-specific indexes

### Missing `JWT_SECRET` causing restart-driven session invalidation
- **Error**:
  - production boot used an ephemeral random fallback secret when `JWT_SECRET` was missing
- **Cause**:
  - auth middleware generated a new random secret on every restart
- **Fix**:
  - production fallback is now stable-derived from deployment-specific env inputs, so restarts no longer rotate the fallback secret
- **Pattern**:
  - explicit `JWT_SECRET` is still preferred, but production fallbacks should be stable if the app must continue booting

### KSA Time Machine UI still exposing EGX-era wording and field names
- **Error**:
  - Time Machine on KSA still showed `Investment Amount (EGP)` and EGP validation text
  - rendered benchmark logic still consumed legacy `egx30_*` payload fields directly
- **Cause**:
  - KSA dashboard reused a partially ported Time Machine frontend
  - backend simulation payload still exposes legacy EGX-shaped benchmark keys
- **Fix**:
  - updated KSA translation strings to `SAR` / `ريال`
  - normalized legacy benchmark payload fields into generic benchmark/TASI values before chart and table rendering
  - updated Time Machine route validation copy and Python log wording to SAR
- **Pattern**:
  - when reusing a cross-market feature, separate payload compatibility from rendered UX
  - legacy API field names can be shimmed in the frontend, but market-specific text must be corrected explicitly

### KSA deployment `/track-record` serving EGX data
- **Error**:
  - `https://xmore-ksa.onrender.com/track-record` displayed EGX track-record content and `.CA` symbols
  - live API evidence included EGX description text, CBE risk-free rate, and EGX top stocks from `/api/track-record/*`
- **Cause**:
  - `web-ui/server.js` served generic `track-record.html` at `/track-record`
  - that page calls generic EGX endpoints under `/api/track-record/*`
- **Fix**:
  - changed KSA deployment route so `/track-record` redirects to `/ksa/track-record`
  - KSA page now uses KSA endpoints under `/api/ksa/track-record/*`
- **Pattern**:
  - on market-specific deployments, public vanity routes must resolve to market-specific pages, not shared generic investor pages

### KSA route handlers using `await` on callback-style DB methods
- **Error**:
  - KSA API endpoints returned `500/502` even when the SQL itself was reasonable
- **Cause**:
  - `web-ui/routes/ksa-signals.js` and `web-ui/routes/ksa-track-record.js` used `await db.all(...)` / `await db.get(...)`
  - but `server.js` exposes `db.all/get/run` as callback-style methods, not promise-returning methods
- **Fix**:
  - added local `dbAll()` and `dbGet()` promise wrappers in both route files
  - switched all awaited calls to those wrappers
- **Pattern**:
  - if a route module uses `async/await`, wrap callback DB adapters first; do not await callback APIs directly

### Full branch validation and live smoke baseline
- **Check**:
  - `main`: `npm run check`, `pytest` -> `52 passed`
  - `xmore-ksa`: `npm run check`, `pytest` -> `52 passed`
  - live smoke passed against both Render deployments
- **Confirmed live endpoints**:
  - `/api/performance-v2/export-summary`
  - `/api/intelligence/changes`
- **Operational note**:
  - `main` does not currently define npm script `smoke:url`; use direct endpoint checks or the KSA smoke runner for cross-branch production validation
- **Observed behavior**:
  - `/api/health` returns `404` on both deployments; treat that as current expected behavior, not a regression

### KSA workflow runtime failures from unsupported CLI flags
- **Error**:
  - `collect_data.py: error: unrecognized arguments: --market KSA`
  - `evaluate.py: error: unrecognized arguments: --market KSA`
  - the KSA news/sentiment/portfolio steps had the same latent mismatch pattern
  - `ModuleNotFoundError: No module named 'agents'` from `python agents/dcf/ksa_dcf_engine.py --force`
- **Cause**:
  - the workflow assumed a shared multi-market CLI surface that these branch-specialized scripts do not expose
  - the DCF engine was invoked by path instead of module form, which broke package imports on GitHub runners
- **Fix**:
  - removed unsupported `--market KSA` flags from KSA workflow commands
  - switched DCF execution to `python -m agents.dcf.ksa_dcf_engine --force`
- **Pattern**:
  - confirm argparse support before adding workflow flags
  - use module execution in CI for scripts that import sibling packages

### GitHub Actions branch checkout drift / scheduled-run limitation
- **Error**: KSA workflows could run the wrong branch because `actions/checkout` was pinned to `main` or `xmore-ksa`.
- **Cause**:
  - hard-coded workflow refs
  - GitHub cron only evaluates workflow files from the default branch
- **Fix**:
  - KSA branch workflows now use `${{ github.ref_name }}`
  - default-branch KSA scheduler added on `main` to check out `xmore-ksa` explicitly
- **Pattern**:
  - branch-aware checkout for dispatch/manual runs
  - default-branch dispatcher for scheduled non-default-branch automation

### Performance metrics importing KSA compatibility aliases as EGX defaults
- **Error**: shared Sharpe test failed because default metrics basis resolved to:
  - annual risk-free `0.05`
  - trading days `252`
- **Cause**: `engines/performance_metrics.py` imported legacy `EGX_*` names from `config/execution_config.py`, where they had been remapped for KSA compatibility.
- **Fix**:
  - pinned EGX reporting defaults directly inside `engines/performance_metrics.py`
  - retained import of `EGX_ROUND_TRIP_RATE` only
- **Result**:
  - performance metrics test suite passes on both branches (`52 passed`)

## Mar 2, 2026

### 1. `evaluate.py` — PostgreSQL boolean type mismatch
- **Error**: `operator does not exist: boolean = integer` on `r.ok = 1`
- **Cause**: `ok BOOLEAN` column in PG can't compare to integer 1
- **Fix**: Changed `r.ok = 1` → `r.ok = TRUE` in both portfolio forecast queries (lines 193, 289)
- **Pattern**: Always use `TRUE`/`FALSE` for BOOLEAN columns in PG. SQLite accepts both `1` and `TRUE`.
- **Check**: `run_agents.py` and `engines/performance_metrics.py` already correctly guard with `if DATABASE_URL:` / `else:` branches

### 2. `web-ui/public/app.js` — `formatDate()` shows "02:00" for date cards
- **Error**: Dashboard "Latest Data" card showed "2026-02-26 02:00" instead of "2026-02-26"
- **Cause**: PostgreSQL `DATE` columns serialize via `pg` client as full ISO timestamps (`"2026-02-26T00:00:00.000Z"`). The old regex `^\d{4}-\d{2}-\d{2}$` didn't match, so JS parsed as UTC midnight → Cairo +02:00 = "02:00"
- **Fix**: `formatDate()` now extracts `YYYY-MM-DD` prefix via `s.match(/^(\d{4}-\d{2}-\d{2})/)` from any ISO string, then parses as local midnight — always returns plain date

### 3. `data/egx_live_scraper.py` — "truth value of a Series is ambiguous"
- **Error**: `WARNING: EGX live feed failed: The truth value of a Series is ambiguous`
- **Cause**: Multiple Arabic column variants (e.g. `إغلاق` and `اغلاق`) both mapped to `'close'` in `_map_columns()`, creating duplicate columns. `df['close']` then returns a DataFrame, not a Series — causing ambiguity in `pd.notna()`, `== 0` filters, etc.
- **Fix**: Added `df = df.loc[:, ~df.columns.duplicated()]` after `df.rename(columns=new_columns)` — keeps first occurrence of each column name
- **Impact**: Was causing EGX live feed to fail on every run, falling back to yfinance silently

---

## Feb 15, 2026

### PG transaction abort in `create_tables()`
- `ALTER TABLE ADD COLUMN` fails in PG if column exists → aborts whole transaction
- Fixed with `_safe_add_column()` using `SAVEPOINT`/`ROLLBACK TO SAVEPOINT` for PG, plain try/except for SQLite

### `INSERT OR IGNORE` (SQLite-only syntax)
- `database.py` EGX stock seeding used SQLite syntax → fails in PG
- Fixed to `INSERT ... ON CONFLICT (symbol) DO NOTHING`

### `utils.py` shadowing `utils/` package
- Root-level `utils.py` shadowed `utils/` directory → `from utils.trading_calendar import ...` broke
- Renamed to `prediction_utils.py`, added `utils/__init__.py`
- **Lesson**: In Python, `foo.py` always shadows `foo/` directory

---

## Recurring PG vs SQLite Patterns
- `BOOLEAN` columns: use `TRUE`/`FALSE` in SQL, never `1`/`0`
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING` for PG
- `CURRENT_DATE - N` works in PG; SQLite needs `date('now', '-N days')`
- `DATE` columns serialize as full ISO timestamps in JSON (pg client) — strip to `YYYY-MM-DD` on frontend
- `_adapt_sql()` in Python scripts handles `?` → `%s` substitution; guard DB-specific SQL with `if DATABASE_URL:`
## Mar 18, 2026
### Docs page Arabic RTL not auto-applying
- **Symptom**: /docs could open in LTR even when the main app was already in Arabic.
- **Cause**: Docs page only read localStorage('docs-lang'), while the rest of the app uses localStorage('lang').
- **Fix**: Added getInitialDocsLang() in web-ui/public/docs.html with precedence:
  1) ?lang= query value
  2) global localStorage('lang')
  3) docs fallback localStorage('docs-lang')
  4) document language / browser fallback
- **Result**: Arabic docs now open RTL automatically and remain synced with site language.
