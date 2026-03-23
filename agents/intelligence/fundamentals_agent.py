"""
Fundamentals Agent — Quarterly financial data via yfinance.
Runs SUNDAY ONLY. Stores in company_fundamentals table.
"""
import json
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CREATE_FUNDAMENTALS_SQL = """
CREATE TABLE IF NOT EXISTS company_fundamentals (
    id                        SERIAL PRIMARY KEY,
    ticker                    VARCHAR(10) NOT NULL,
    fetched_at                TIMESTAMPTZ DEFAULT NOW(),
    market_cap                BIGINT,
    current_price             NUMERIC(10,2),
    pe_ratio                  NUMERIC(8,2),
    pb_ratio                  NUMERIC(8,2),
    ps_ratio                  NUMERIC(8,2),
    eps_ttm                   NUMERIC(8,2),
    revenue_ttm               BIGINT,
    net_income_ttm            BIGINT,
    profit_margin             NUMERIC(6,4),
    revenue_growth_yoy        NUMERIC(6,4),
    earnings_growth_yoy       NUMERIC(6,4),
    debt_to_equity            NUMERIC(8,2),
    current_ratio             NUMERIC(6,2),
    quick_ratio               NUMERIC(6,2),
    roe                       NUMERIC(6,4),
    roa                       NUMERIC(6,4),
    week52_high               NUMERIC(10,2),
    week52_low                NUMERIC(10,2),
    price_to_52w_high         NUMERIC(6,4),
    price_to_52w_low          NUMERIC(6,4),
    dividend_yield            NUMERIC(6,4),
    payout_ratio              NUMERIC(6,4),
    avg_volume_10d            BIGINT,
    avg_volume_3m             BIGINT,
    beta                      NUMERIC(6,3),
    shares_outstanding        BIGINT,
    float_shares              BIGINT,
    insider_ownership_pct     NUMERIC(6,3),
    institution_ownership_pct NUMERIC(6,3),
    institutional_holders     TEXT,
    quarterly_revenue         TEXT,
    quarterly_net_income      TEXT,
    near_52w_high             BOOLEAN,
    near_52w_low              BOOLEAN,
    value_flag                BOOLEAN,
    momentum_flag             BOOLEAN,
    UNIQUE (ticker, fetched_at::date)
)
"""

CREATE_FUNDAMENTALS_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS company_fundamentals (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                    TEXT NOT NULL,
    fetched_at                TEXT DEFAULT (datetime('now')),
    market_cap                INTEGER,
    current_price             REAL,
    pe_ratio                  REAL,
    pb_ratio                  REAL,
    ps_ratio                  REAL,
    eps_ttm                   REAL,
    revenue_ttm               INTEGER,
    net_income_ttm            INTEGER,
    profit_margin             REAL,
    revenue_growth_yoy        REAL,
    earnings_growth_yoy       REAL,
    debt_to_equity            REAL,
    current_ratio             REAL,
    quick_ratio               REAL,
    roe                       REAL,
    roa                       REAL,
    week52_high               REAL,
    week52_low                REAL,
    price_to_52w_high         REAL,
    price_to_52w_low          REAL,
    dividend_yield            REAL,
    payout_ratio              REAL,
    avg_volume_10d            INTEGER,
    avg_volume_3m             INTEGER,
    beta                      REAL,
    shares_outstanding        INTEGER,
    float_shares              INTEGER,
    insider_ownership_pct     REAL,
    institution_ownership_pct REAL,
    institutional_holders     TEXT,
    quarterly_revenue         TEXT,
    quarterly_net_income      TEXT,
    near_52w_high             INTEGER,
    near_52w_low              INTEGER,
    value_flag                INTEGER,
    momentum_flag             INTEGER
)
"""

FIELD_MAP = {
    "marketCap":                        "market_cap",
    "currentPrice":                     "current_price",
    "trailingPE":                       "pe_ratio",
    "priceToBook":                      "pb_ratio",
    "priceToSalesTrailing12Months":     "ps_ratio",
    "trailingEps":                      "eps_ttm",
    "totalRevenue":                     "revenue_ttm",
    "netIncomeToCommon":                "net_income_ttm",
    "profitMargins":                    "profit_margin",
    "revenueGrowth":                    "revenue_growth_yoy",
    "earningsGrowth":                   "earnings_growth_yoy",
    "debtToEquity":                     "debt_to_equity",
    "currentRatio":                     "current_ratio",
    "quickRatio":                       "quick_ratio",
    "returnOnEquity":                   "roe",
    "returnOnAssets":                   "roa",
    "fiftyTwoWeekHigh":                 "week52_high",
    "fiftyTwoWeekLow":                  "week52_low",
    "dividendYield":                    "dividend_yield",
    "payoutRatio":                      "payout_ratio",
    "averageVolume10days":              "avg_volume_10d",
    "averageVolume":                    "avg_volume_3m",
    "beta":                             "beta",
    "sharesOutstanding":                "shares_outstanding",
    "floatShares":                      "float_shares",
}


def ensure_fundamentals_table(conn):
    from database import DATABASE_URL
    cursor = conn.cursor()
    sql = CREATE_FUNDAMENTALS_SQL if DATABASE_URL else CREATE_FUNDAMENTALS_SQL_SQLITE
    # Postgres UNIQUE on expression requires different handling
    if DATABASE_URL:
        try:
            cursor.execute("SAVEPOINT create_fundamentals")
            cursor.execute(sql.replace("UNIQUE (ticker, fetched_at::date)", ""))
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fund_ticker_date ON company_fundamentals(ticker, fetched_at::date)")
            cursor.execute("RELEASE SAVEPOINT create_fundamentals")
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT create_fundamentals")
    else:
        cursor.execute(sql)
        # SQLite doesn't allow expressions in UNIQUE constraints — use a separate index
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fund_ticker_date ON company_fundamentals(ticker, date(fetched_at))")
        except Exception:
            pass


def run_fundamentals(conn) -> int:
    if datetime.today().weekday() != 6:
        logger.info("[INTEL:FUNDAMENTALS] Skipping — runs Sundays only")
        return 0

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[INTEL:FUNDAMENTALS] yfinance not installed — skipping")
        return 0

    from database import DATABASE_URL, _adapt_sql
    from agents.intelligence.market_universe import TICKER_ROWS

    ensure_fundamentals_table(conn)
    cursor = conn.cursor()
    count  = 0

    for ticker, yahoo, *_ in TICKER_ROWS:
        try:
            stock = yf.Ticker(yahoo)
            info  = stock.info or {}
            time.sleep(2.0)

            row = {}
            for yf_key, db_key in FIELD_MAP.items():
                val = info.get(yf_key)
                try:
                    row[db_key] = float(val) if val is not None else None
                except (TypeError, ValueError):
                    row[db_key] = None

            # Computed fields
            price = row.get("current_price") or 0
            hi52  = row.get("week52_high") or 1
            lo52  = row.get("week52_low") or 1
            row["price_to_52w_high"] = round(price / hi52, 4) if hi52 and price else None
            row["price_to_52w_low"]  = round(price / lo52, 4) if lo52 and price else None
            row["near_52w_high"]  = bool((row["price_to_52w_high"] or 0) > 0.95)
            row["near_52w_low"]   = bool((row["price_to_52w_high"] or 1) < 0.70)
            pe = row.get("pe_ratio") or 99
            pb = row.get("pb_ratio") or 99
            row["value_flag"]    = bool(pe < 10 and pb < 1.5)
            eg = row.get("earnings_growth_yoy") or 0
            row["momentum_flag"] = bool(row["near_52w_high"] and eg > 0)

            # Quarterly revenue
            try:
                qf = stock.quarterly_financials
                if qf is not None and not qf.empty and "Total Revenue" in qf.index:
                    qrev = []
                    for col in qf.columns[:4]:
                        rev = qf.loc["Total Revenue", col]
                        qrev.append({"q": str(col.date()), "revenue": int(rev) if rev == rev else None})
                    row["quarterly_revenue"] = json.dumps(qrev)
            except Exception as e:
                logger.debug(f"[INTEL:FUNDAMENTALS] {ticker}: quarterly revenue parse failed: {e}")

            # Ownership
            try:
                major = stock.major_holders
                if major is not None and not major.empty:
                    row["insider_ownership_pct"]     = float(major.iloc[0, 0]) if len(major) > 0 else None
                    row["institution_ownership_pct"] = float(major.iloc[1, 0]) if len(major) > 1 else None
            except Exception as e:
                logger.debug(f"[INTEL:FUNDAMENTALS] {ticker}: ownership parse failed: {e}")

            ph = "%s" if DATABASE_URL else "?"
            cols = ", ".join(["ticker"] + list(row.keys()))
            vals = ", ".join([ph] * (len(row) + 1))
            update_set = ", ".join(f"{k}=EXCLUDED.{k}" if DATABASE_URL else f"{k}={ph}" for k in row.keys())

            if DATABASE_URL:
                cursor.execute(
                    f"INSERT INTO company_fundamentals ({cols}) VALUES ({vals})"
                    f" ON CONFLICT (ticker, fetched_at::date) DO UPDATE SET {update_set}",
                    [ticker] + list(row.values())
                )
            else:
                cursor.execute(
                    f"INSERT OR REPLACE INTO company_fundamentals ({cols}) VALUES ({vals})",
                    [ticker] + list(row.values())
                )
            count += 1
            logger.info(f"[INTEL:FUNDAMENTALS] {ticker}: P/E={row.get('pe_ratio')}, MCap={row.get('market_cap')}")

        except Exception as e:
            logger.error(f"[INTEL:FUNDAMENTALS] {ticker}: {e}")

    logger.info(f"[INTEL:FUNDAMENTALS] {count} companies updated")
    return count
