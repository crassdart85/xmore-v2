"""
fix_stale_evaluations.py

Deletes evaluations where actual_change_pct = 0.0 (stock appeared flat —
likely caused by stale yfinance data where start_price == end_price).
These will be re-evaluated on the next catchup-evaluation run with correct prices.

Run once on production:
  python fix_stale_evaluations.py
"""
import os
from database import get_connection

DATABASE_URL = os.getenv('DATABASE_URL')

def _adapt_sql(sql):
    return sql.replace('?', '%s') if DATABASE_URL else sql

with get_connection() as conn:
    cur = conn.cursor()

    # Count affected rows
    cur.execute(_adapt_sql("SELECT COUNT(*) FROM evaluations WHERE actual_change_pct = ?"), (0.0,))
    row = cur.fetchone()
    count = row[0] if row else 0
    print(f"Found {count} evaluations with 0.0% change (likely stale price artifact)")

    if count == 0:
        print("Nothing to clean up.")
    else:
        cur.execute(_adapt_sql("DELETE FROM evaluations WHERE actual_change_pct = ?"), (0.0,))
        print(f"Deleted {count} rows. They will re-evaluate on next catchup-evaluation run.")

print("Done.")
