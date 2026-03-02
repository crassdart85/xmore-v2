"""
engines/etf_premium_discount.py — Compute ETF premium/discount (market price vs NAV).

Logic:
  For each instrument, JOIN latest etf_price_daily + latest etf_nav.
  premium_discount = (market_price - nav_value) / nav_value

Output: etf_premium_discount_daily

Run:
    python -m engines.etf_premium_discount
"""

import os
import sys
import logging
import time

from database import create_tables, get_connection, _adapt_sql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def run():
    is_pg = bool(os.getenv('DATABASE_URL'))
    ph = '%s' if is_pg else '?'
    computed = 0

    with get_connection() as conn:
        cur = conn.cursor()

        # Find instruments that have BOTH a recent price AND a recent NAV
        # (within the last 7 days for price, 30 days for NAV)
        cur.execute(_adapt_sql("""
            SELECT
                p.instrument_id,
                p.trade_date        AS price_date,
                p.last_price        AS market_price,
                n.nav_date,
                n.nav_value
            FROM (
                SELECT instrument_id, MAX(trade_date) AS max_date
                FROM etf_price_daily
                WHERE trade_date >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY instrument_id
            ) latest_p
            JOIN etf_price_daily p
                ON p.instrument_id = latest_p.instrument_id
               AND p.trade_date    = latest_p.max_date
               AND p.last_price IS NOT NULL
            JOIN (
                SELECT instrument_id, MAX(nav_date) AS max_date
                FROM etf_nav
                WHERE nav_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY instrument_id
            ) latest_n
                ON latest_n.instrument_id = p.instrument_id
            JOIN etf_nav n
                ON n.instrument_id = latest_n.instrument_id
               AND n.nav_date      = latest_n.max_date
               AND n.nav_value IS NOT NULL
               AND n.nav_value > 0
        """ if is_pg else """
            SELECT
                p.instrument_id,
                p.trade_date        AS price_date,
                p.last_price        AS market_price,
                n.nav_date,
                n.nav_value
            FROM (
                SELECT instrument_id, MAX(trade_date) AS max_date
                FROM etf_price_daily
                WHERE trade_date >= date('now', '-7 days')
                GROUP BY instrument_id
            ) latest_p
            JOIN etf_price_daily p
                ON p.instrument_id = latest_p.instrument_id
               AND p.trade_date    = latest_p.max_date
               AND p.last_price IS NOT NULL
            JOIN (
                SELECT instrument_id, MAX(nav_date) AS max_date
                FROM etf_nav
                WHERE nav_date >= date('now', '-30 days')
                GROUP BY instrument_id
            ) latest_n
                ON latest_n.instrument_id = p.instrument_id
            JOIN etf_nav n
                ON n.instrument_id = latest_n.instrument_id
               AND n.nav_date      = latest_n.max_date
               AND n.nav_value IS NOT NULL
               AND n.nav_value > 0
        """))

        rows = cur.fetchall()
        if not rows:
            logger.info('[etf_premium_discount] No matching price+NAV pairs found')
            return 0

        for row in rows:
            if hasattr(row, 'keys'):
                # dict-like (psycopg2 RealDictCursor or sqlite3 Row)
                inst_id      = row['instrument_id']
                asof_date    = row['price_date']
                market_price = row['market_price']
                nav_date     = row['nav_date']
                nav_value    = row['nav_value']
            else:
                inst_id, asof_date, market_price, nav_date, nav_value = row

            prem_disc = (market_price - nav_value) / nav_value
            notes = None
            if str(asof_date) != str(nav_date):
                notes = f'Price date {asof_date} ≠ NAV date {nav_date}'
                logger.debug('[etf_premium_discount] %s', notes)

            conflict = (
                'ON CONFLICT (instrument_id, asof_date) DO UPDATE SET '
                'market_price=EXCLUDED.market_price, nav_value=EXCLUDED.nav_value, '
                'premium_discount=EXCLUDED.premium_discount, nav_date_used=EXCLUDED.nav_date_used, '
                'calc_notes=EXCLUDED.calc_notes'
            ) if is_pg else (
                'ON CONFLICT(instrument_id, asof_date) DO UPDATE SET '
                'market_price=excluded.market_price, nav_value=excluded.nav_value, '
                'premium_discount=excluded.premium_discount, nav_date_used=excluded.nav_date_used, '
                'calc_notes=excluded.calc_notes'
            )

            sql = _adapt_sql(f"""
                INSERT INTO etf_premium_discount_daily
                  (instrument_id, asof_date, market_price, nav_value, premium_discount, nav_date_used, calc_notes)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})
                {conflict}
            """)
            try:
                cur.execute(sql, (inst_id, asof_date, market_price, nav_value, prem_disc, nav_date, notes))
                computed += 1
                logger.debug('[etf_premium_discount] inst %s: P/D = %.4f%%', inst_id, prem_disc * 100)
            except Exception as exc:
                logger.error('[etf_premium_discount] inst %s: %s', inst_id, exc)

    logger.info('[etf_premium_discount] Done — %d premium/discount rows computed', computed)
    return computed


if __name__ == '__main__':
    start = time.time()
    try:
        create_tables()
        count = run()
        from database import log_system_run
        log_system_run('etf_premium_discount', 'success', f'{count} rows', time.time() - start)
    except Exception as exc:
        logger.exception('[etf_premium_discount] Fatal: %s', exc)
        try:
            from database import log_system_run
            log_system_run('etf_premium_discount', 'failure', str(exc), time.time() - start)
        except Exception:
            pass
        sys.exit(1)
