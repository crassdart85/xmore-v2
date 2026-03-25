# Xmore Bug Fix Log

## Mar 25, 2026

### Full branch validation and live smoke baseline
- **Check**:
  - `main`: `npm run check`, `pytest` -> `52 passed`
  - `xmore-ksa`: `npm run check`, `pytest` -> `52 passed`
  - live smoke passed against both Render deployments
- **Confirmed live endpoints**:
  - `/api/performance-v2/export-summary`
  - `/api/intelligence/changes`
- **Operational note**:
  - `main` does not currently define npm script `smoke:url`; use direct endpoint checks or the KSA branch smoke runner when validating production from this repo state
- **Observed behavior**:
  - `/api/health` returns `404` on both deployments; this is current expected behavior until a health route is added

### KSA workflow runtime failures from unsupported CLI flags
- **Error**:
  - `collect_data.py: error: unrecognized arguments: --market KSA`
  - `evaluate.py: error: unrecognized arguments: --market KSA`
  - KSA News RAG and sentiment/portfolio steps had the same latent mismatch pattern
  - `ModuleNotFoundError: No module named 'agents'` from `python agents/dcf/ksa_dcf_engine.py --force`
- **Cause**:
  - KSA workflows were written as if shared scripts exposed a `--market KSA` switch
  - on `xmore-ksa`, those scripts are already branch-specialized and do not expose that CLI
  - the DCF engine was invoked by file path, which broke package imports on GitHub runners
- **Fix**:
  - removed unsupported `--market KSA` flags from the KSA workflow commands
  - switched DCF execution to module form: `python -m agents.dcf.ksa_dcf_engine --force`
- **Pattern**:
  - before adding market flags to scheduled jobs, validate the script's argparse surface with `--help`
  - use `python -m package.module` for package-based entry points in CI when imports depend on repo-root module resolution

### GitHub Actions branch checkout drift / default-branch scheduler gap
- **Error**: workflows on both EGY and KSA branches were forcing `actions/checkout` to `ref: main` or `ref: xmore-ksa`, causing branch-dispatch runs to execute the wrong code.
- **Cause**:
  - workflow YAML had hard-coded checkout refs
  - GitHub scheduled workflows only load from the repository default branch
- **Fix**:
  - branch-owned workflows now use `${{ github.ref_name }}`
  - added `main` workflow `.github/workflows/ksa-branch-scheduled.yml` that runs on the KSA cron schedule but checks out `xmore-ksa`
- **Pattern**:
  - use `${{ github.ref_name }}` for normal branch-aware workflow execution
  - use a default-branch dispatcher when scheduled automation must target a non-default branch

### Performance metrics loading KSA compatibility aliases as EGX defaults
- **Error**: `tests/test_performance_metrics.py::test_sharpe_uses_egx_rate_not_us` failed on both branches because default Sharpe inputs were effectively:
  - risk-free rate `0.05`
  - trading days `252`
- **Cause**: `engines/performance_metrics.py` imported legacy `EGX_*` names from `config/execution_config.py`, but those names had been repurposed there for Tadawul/KSA compatibility.
- **Fix**:
  - pinned EGX reporting defaults locally in `engines/performance_metrics.py`
  - kept only `EGX_ROUND_TRIP_RATE` imported from execution config
- **Result**:
  - EGX metrics again use `27.25%` annual risk-free and `247` trading days
  - full suite passes (`52 passed`) on both branches

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
