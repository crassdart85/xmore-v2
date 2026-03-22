"""
KSA Fundamentals Agent — fetches company fundamentals for KSA_TOP50 via yfinance.
Runs Sundays only. Stores in ksa_company_fundamentals table.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MARKET_ID = "KSA"


def fetch_ksa_fundamentals(conn) -> None:
    """Sunday-only fundamentals fetch. Non-fatal."""
    if datetime.now().weekday() != 6:
        logger.info("[KSA] Fundamentals: not Sunday — skipping")
        return
    try:
        _run_fundamentals(conn)
    except Exception as e:
        logger.warning(f"[KSA] Fundamentals error (non-fatal): {e}")


def _run_fundamentals(conn):
    import yfinance as yf
    from config.ksa_universe import KSA_TOP50, KSA_BANKING_TICKERS

    _ensure_table(conn)
    updated = 0

    for row in KSA_TOP50:
        yf_ticker = row["symbol"]
        name_en   = row.get("name_en", yf_ticker)
        name_ar   = row.get("name_ar", yf_ticker)
        sector    = row.get("sector_en", "")
        try:
            info = yf.Ticker(yf_ticker).info
            if not info:
                continue

            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ksa_company_fundamentals
                    (ticker, market_id, company_name_en, company_name_ar, sector,
                     market_cap_sar, pe_ratio, pb_ratio, dividend_yield,
                     revenue_sar, net_income_sar, total_assets_sar, total_debt_sar,
                     free_cashflow_sar, beta,
                     week_52_high, week_52_low,
                     near_52w_high, near_52w_low,
                     value_flag, momentum_flag,
                     is_banking, updated_at)
                VALUES (%s,'KSA',%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s, %s, NOW())
                ON CONFLICT (ticker) DO UPDATE SET
                    market_cap_sar = EXCLUDED.market_cap_sar,
                    pe_ratio       = EXCLUDED.pe_ratio,
                    pb_ratio       = EXCLUDED.pb_ratio,
                    dividend_yield = EXCLUDED.dividend_yield,
                    week_52_high   = EXCLUDED.week_52_high,
                    week_52_low    = EXCLUDED.week_52_low,
                    near_52w_high  = EXCLUDED.near_52w_high,
                    near_52w_low   = EXCLUDED.near_52w_low,
                    value_flag     = EXCLUDED.value_flag,
                    momentum_flag  = EXCLUDED.momentum_flag,
                    updated_at     = NOW()
            """, (
                yf_ticker, name_en, name_ar, sector,
                info.get("marketCap"),
                info.get("trailingPE"),
                info.get("priceToBook"),
                info.get("dividendYield"),
                info.get("totalRevenue"),
                info.get("netIncomeToCommon"),
                info.get("totalAssets"),
                info.get("totalDebt"),
                info.get("freeCashflow"),
                info.get("beta"),
                info.get("fiftyTwoWeekHigh"),
                info.get("fiftyTwoWeekLow"),
                _near_high(info),
                _near_low(info),
                _value_flag(info),
                _momentum_flag(info),
                yf_ticker in KSA_BANKING_TICKERS,
            ))
            conn.commit()
            cur.close()
            updated += 1

        except Exception as e:
            logger.debug(f"[KSA] Fundamentals {yf_ticker}: {e}")

    logger.info(f"[KSA] Fundamentals: {updated} companies updated")


def _near_high(info) -> bool:
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    high  = info.get("fiftyTwoWeekHigh")
    if price and high and high > 0:
        return (price / high) >= 0.95
    return False


def _near_low(info) -> bool:
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    low   = info.get("fiftyTwoWeekLow")
    if price and low and low > 0:
        return (price / low) <= 1.05
    return False


def _value_flag(info) -> bool:
    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    return bool(pe and pe < 15 and pb and pb < 1.5)


def _momentum_flag(info) -> bool:
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    high  = info.get("fiftyTwoWeekHigh")
    if price and high and high > 0:
        return (price / high) >= 0.90
    return False


def _ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ksa_company_fundamentals (
                ticker VARCHAR(20) PRIMARY KEY,
                market_id VARCHAR(10) DEFAULT 'KSA',
                company_name_en VARCHAR(200),
                company_name_ar VARCHAR(200),
                sector VARCHAR(100),
                market_cap_sar NUMERIC(20,2),
                pe_ratio NUMERIC(10,2),
                pb_ratio NUMERIC(10,2),
                dividend_yield NUMERIC(6,4),
                revenue_sar NUMERIC(20,2),
                net_income_sar NUMERIC(20,2),
                total_assets_sar NUMERIC(20,2),
                total_debt_sar NUMERIC(20,2),
                free_cashflow_sar NUMERIC(20,2),
                beta NUMERIC(6,4),
                week_52_high NUMERIC(12,2),
                week_52_low NUMERIC(12,2),
                near_52w_high BOOLEAN DEFAULT FALSE,
                near_52w_low BOOLEAN DEFAULT FALSE,
                value_flag BOOLEAN DEFAULT FALSE,
                momentum_flag BOOLEAN DEFAULT FALSE,
                shariah_compliant BOOLEAN DEFAULT NULL,
                is_banking BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
