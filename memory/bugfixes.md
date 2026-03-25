# Xmore Bug Fix Log

## Mar 25, 2026

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
