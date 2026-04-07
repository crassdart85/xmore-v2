"""
Historical Price Backfill Script
=================================
One-time (or re-runnable) script to populate the prices table with 5 years of
daily OHLCV data from Yahoo Finance.

Why this matters
----------------
- ML LightGBM needs 750–1250 trading days for reliable pattern learning
- HMM regime detection needs 200+ daily returns
- GARCH volatility needs 252+ observations
- Walk-forward backtest 90-day train windows are meaningless with < 6 months data

collect_data.py stays at period="90d" for fast daily incremental updates.
This script is the one-time seeder — run it once, then daily runs maintain the gap.

Usage
-----
    python backfill_history.py                    # EGX stocks (default)
    python backfill_history.py --market KSA       # Tadawul stocks
    python backfill_history.py --market ALL       # Both markets
    python backfill_history.py --years 3          # Shorter history (default: 5)
    python backfill_history.py --dry-run          # Print plan, no DB writes
"""

import argparse
import math
import os
import sys
import time
import logging
from datetime import datetime, timedelta

import yfinance as yf

# ── stdlib logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_connection():
    from database import get_connection
    return get_connection()


def _ensure_schema():
    from database import create_tables
    create_tables()


def _upsert_sql():
    if DATABASE_URL:
        return """
            INSERT INTO prices (symbol, date, open, high, low, close, volume, data_source)
            VALUES %s
            ON CONFLICT (symbol, date) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume,
                data_source=EXCLUDED.data_source
        """
    return """
        INSERT OR REPLACE INTO prices
        (symbol, date, open, high, low, close, volume, data_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """


def _existing_row_count(symbol: str) -> int:
    """Return how many price rows already exist for this symbol."""
    try:
        sql = "SELECT COUNT(*) FROM prices WHERE symbol = ?" if not DATABASE_URL \
              else "SELECT COUNT(*) FROM prices WHERE symbol = %s"
        with _get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (symbol,))
            row = cur.fetchone()
            if not row:
                return 0
            if isinstance(row, dict):
                return int(next(iter(row.values())))
            return int(row[0])
    except Exception:
        return 0


def _existing_row_counts(symbols: list[str]) -> dict[str, int]:
    """Return existing price-row counts for a batch of symbols."""
    if not symbols:
        return {}

    try:
        with _get_connection() as conn:
            cur = conn.cursor()
            if DATABASE_URL:
                cur.execute(
                    "SELECT symbol, COUNT(*) AS cnt FROM prices WHERE symbol = ANY(%s) GROUP BY symbol",
                    (symbols,),
                )
            else:
                placeholders = ", ".join(["?"] * len(symbols))
                cur.execute(
                    f"SELECT symbol, COUNT(*) AS cnt FROM prices WHERE symbol IN ({placeholders}) GROUP BY symbol",
                    symbols,
                )

            rows = cur.fetchall() or []
            counts = {}
            for row in rows:
                if isinstance(row, dict):
                    counts[str(row.get("symbol"))] = int(row.get("cnt", 0))
                else:
                    counts[str(row[0])] = int(row[1])
            return counts
    except Exception:
        return {}


def _bulk_upsert_rows(cur, rows: list[tuple]):
    if not rows:
        return 0

    if DATABASE_URL:
        from psycopg2.extras import execute_values
        execute_values(cur, _upsert_sql(), rows, page_size=1000)
        return len(rows)

    cur.executemany(_upsert_sql(), rows)
    return len(rows)


# ── Symbol lists ─────────────────────────────────────────────────────────────

def _egx_symbols():
    try:
        from config import EGX_STOCKS
        return list(EGX_STOCKS)
    except Exception as e:
        logger.warning("Could not import EGX_STOCKS from config: %s", e)
        return []


def _ksa_symbols():
    try:
        from config.ksa_universe import KSA_TOP50
        return [s["symbol"] for s in KSA_TOP50]
    except Exception as e:
        logger.warning("Could not import KSA_TOP50: %s", e)
        return []


def _macro_symbols():
    """Macro instruments needed for ML features."""
    return {
        "MACRO_BRENT":  "BZ=F",
        "MACRO_USDSAR": "SAR=X",
        "MACRO_EEM":    "EEM",
    }


# ── Core fetch + store ────────────────────────────────────────────────────────

def _fetch_and_store(symbol: str, yf_symbol: str, years: int, dry_run: bool) -> dict:
    """
    Fetch `years` years of daily history for `yf_symbol` and store under `symbol`.

    Returns a result dict: {symbol, rows_fetched, rows_new, skipped, error}
    """
    result = {"symbol": symbol, "rows_fetched": 0, "rows_new": 0, "skipped": False, "error": None}

    try:
        existing = _existing_row_count(symbol)

        # If we already have > years*200 rows, this symbol is well-stocked — skip
        threshold = years * 200
        if existing >= threshold:
            logger.info("  SKIP %-18s (already %d rows >= %d threshold)", symbol, existing, threshold)
            result["skipped"] = True
            return result

        period = f"{years}y"
        logger.info("  FETCH %-18s  period=%s  existing=%d rows", symbol, period, existing)

        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, auto_adjust=True)

        if df is None or len(df) == 0:
            result["error"] = "yfinance returned empty DataFrame"
            logger.warning("  WARN  %-18s: no data", symbol)
            return result

        result["rows_fetched"] = len(df)

        if dry_run:
            logger.info("  DRY   %-18s: would insert up to %d rows", symbol, len(df))
            return result

        sql = _upsert_sql()
        insert_rows = []
        with _get_connection() as conn:
            cur = conn.cursor()
            for date, row in df.iterrows():
                try:
                    if any(math.isnan(float(row[col])) for col in ("Open", "High", "Low", "Close")):
                        continue
                    volume = row.get("Volume", 0)
                    volume = 0 if volume is None or (isinstance(volume, float) and math.isnan(volume)) else int(volume)
                    insert_rows.append((
                        symbol,
                        date.strftime("%Y-%m-%d"),
                        float(row["Open"]),
                        float(row["High"]),
                        float(row["Low"]),
                        float(row["Close"]),
                        volume,
                        "yfinance_backfill",
                    ))
                except Exception as row_err:
                    logger.debug("Row error %s %s: %s", symbol, date, row_err)

            inserted = _bulk_upsert_rows(cur, insert_rows)

        result["rows_new"] = inserted
        logger.info("  OK    %-18s: %d rows stored (total was %d)", symbol, inserted, existing)

    except Exception as e:
        result["error"] = str(e)
        logger.error("  ERROR %-18s: %s", symbol, e)

    return result


def _batch_fetch_yfinance(symbols_map: dict, years: int, dry_run: bool) -> list:
    """
    Batch-download using yf.download for efficiency (fewer API calls),
    then store each symbol individually.

    symbols_map: {internal_symbol: yf_symbol}
    """
    results = []
    yf_symbols = list(symbols_map.values())
    existing_counts = _existing_row_counts(list(symbols_map.keys()))

    logger.info("Batch-downloading %d symbols via yf.download ...", len(yf_symbols))
    try:
        data = yf.download(
            tickers=yf_symbols,
            period=f"{years}y",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        logger.warning("Batch download failed (%s) — falling back to per-symbol", e)
        data = None

    for internal_sym, yf_sym in symbols_map.items():
        try:
            existing = existing_counts.get(internal_sym, 0)
            threshold = years * 200
            if existing >= threshold:
                logger.info("  SKIP %-18s (already %d rows)", internal_sym, existing)
                results.append({"symbol": internal_sym, "rows_fetched": 0, "rows_new": 0, "skipped": True, "error": None})
                continue  # already well-stocked

            # Extract this symbol's slice from batch data
            if data is not None and not data.empty:
                try:
                    if len(yf_symbols) == 1:
                        df = data
                    else:
                        df = data[yf_sym] if yf_sym in data.columns.get_level_values(0) else None
                except Exception:
                    df = None
            else:
                df = None

            if df is None or (hasattr(df, "__len__") and len(df) == 0):
                # Fallback: individual fetch
                r = _fetch_and_store(internal_sym, yf_sym, years, dry_run)
                results.append(r)
                continue

            rows_fetched = len(df)
            logger.info("  STORE %-18s: %d rows from batch", internal_sym, rows_fetched)

            if dry_run:
                results.append({"symbol": internal_sym, "rows_fetched": rows_fetched, "rows_new": 0, "skipped": False, "error": None})
                continue

            inserted = 0
            with _get_connection() as conn:
                cur = conn.cursor()
                insert_rows = []
                for date, row in df.iterrows():
                    try:
                        close = float(row.get("Close", row.get("close", 0)))
                        if close == 0:
                            continue
                        volume = row.get("Volume", 0)
                        volume = 0 if volume is None or (isinstance(volume, float) and math.isnan(volume)) else int(volume)
                        insert_rows.append((
                            internal_sym,
                            date.strftime("%Y-%m-%d"),
                            float(row.get("Open", close)),
                            float(row.get("High", close)),
                            float(row.get("Low", close)),
                            close,
                            volume,
                            "yfinance_backfill",
                        ))
                    except Exception as row_err:
                        logger.debug("Row error %s %s: %s", internal_sym, date, row_err)

                inserted = _bulk_upsert_rows(cur, insert_rows)

            results.append({"symbol": internal_sym, "rows_fetched": rows_fetched, "rows_new": inserted, "skipped": False, "error": None})
            logger.info("  OK    %-18s: %d rows stored", internal_sym, inserted)

        except Exception as e:
            results.append({"symbol": internal_sym, "rows_fetched": 0, "rows_new": 0, "skipped": False, "error": str(e)})
            logger.error("  ERROR %-18s: %s", internal_sym, e)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def run_backfill(market: str = "EGX", years: int = 5, dry_run: bool = False):
    start_ts = datetime.utcnow()
    _ensure_schema()
    print(f"\n{'='*60}")
    print(f"  Historical Price Backfill")
    print(f"  Market: {market}  |  Years: {years}  |  Dry-run: {dry_run}")
    print(f"  DB: {'PostgreSQL' if DATABASE_URL else 'SQLite (local)'}")
    print(f"{'='*60}\n")

    all_results = []

    # ── EGX stocks ──
    if market in ("EGX", "ALL"):
        egx_syms = _egx_symbols()
        if not egx_syms:
            logger.warning("No EGX symbols found — check config.EGX_STOCKS")
        else:
            print(f"[EGX] {len(egx_syms)} stocks - fetching {years}-year history\n")
            # EGX stocks use .CA suffix on yfinance
            sym_map = {s: s for s in egx_syms}  # symbol == yf symbol for EGX
            results = _batch_fetch_yfinance(sym_map, years, dry_run)
            all_results.extend(results)
            # Brief pause between batches
            if not dry_run:
                time.sleep(2)

    # ── KSA stocks ──
    if market in ("KSA", "ALL"):
        ksa_syms = _ksa_symbols()
        if not ksa_syms:
            logger.warning("No KSA symbols found — check config/ksa_universe.py")
        else:
            print(f"\n[KSA] {len(ksa_syms)} stocks - fetching {years}-year history\n")
            sym_map = {s: s for s in ksa_syms}  # symbol == yf symbol (.SR suffix)
            results = _batch_fetch_yfinance(sym_map, years, dry_run)
            all_results.extend(results)
            if not dry_run:
                time.sleep(2)

    # ── Macro instruments ──
    print(f"\n[MACRO] Fetching macro instruments ({years}y)\n")
    macro_map = _macro_symbols()
    macro_results = _batch_fetch_yfinance(macro_map, years, dry_run)
    all_results.extend(macro_results)

    # ── Summary ──
    elapsed = (datetime.utcnow() - start_ts).total_seconds()
    ok      = [r for r in all_results if not r.get("error") and not r.get("skipped")]
    skipped = [r for r in all_results if r.get("skipped")]
    errors  = [r for r in all_results if r.get("error")]
    total_rows = sum(r.get("rows_new", 0) for r in all_results)

    print(f"\n{'='*60}")
    print(f"  Backfill complete in {elapsed:.0f}s")
    print(f"  Symbols processed : {len(all_results)}")
    print(f"  Successful        : {len(ok)}")
    print(f"  Skipped (>=target): {len(skipped)}")
    print(f"  Errors            : {len(errors)}")
    print(f"  Total rows stored : {total_rows:,}")
    print(f"{'='*60}")

    if errors:
        print("\nFailed symbols:")
        for r in errors:
            print(f"  {r['symbol']}: {r['error']}")

    return len(errors) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill historical price data")
    parser.add_argument("--market", choices=["EGX", "KSA", "ALL"], default="EGX",
                        help="Which market to backfill (default: EGX)")
    parser.add_argument("--years", type=int, default=5,
                        help="Years of history to fetch (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan without writing to DB")
    args = parser.parse_args()

    success = run_backfill(market=args.market, years=args.years, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
