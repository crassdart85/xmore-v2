"""
Evaluate past trade recommendations against actual price movements.
Runs daily to fill in actual_next_day_return, actual_5day_return, was_correct.
"""

from database import get_connection
import os

def evaluate_past_recommendations():
    """
    Look back at recommendations from 1 and 5 trading days ago.
    Compare recommended action against actual price movement.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Evaluate 1-day-old recommendations
        if os.getenv('DATABASE_URL'):
            cursor.execute("""
                SELECT tr.id, tr.symbol,
                       COALESCE(tr.action, tr.signal_type, tr.signal) AS action,
                       tr.signal, tr.close_price,
                       tr.recommendation_date
                FROM trade_recommendations tr
                WHERE tr.actual_next_day_return IS NULL
                AND tr.recommendation_date <= CURRENT_DATE - INTERVAL '1 day'
                AND tr.recommendation_date >= CURRENT_DATE - INTERVAL '10 days'
            """)
        else:
             cursor.execute("""
                SELECT tr.id, tr.symbol,
                       COALESCE(tr.action, tr.signal_type, tr.signal) AS action,
                       tr.signal, tr.close_price,
                       tr.recommendation_date
                FROM trade_recommendations tr
                WHERE tr.actual_next_day_return IS NULL
                AND tr.recommendation_date <= date('now', '-1 day')
                AND tr.recommendation_date >= date('now', '-10 days')
            """)
            
        recs_1d = [dict(row) for row in cursor.fetchall()]
        
        for rec in recs_1d:
            # Get next trading day's close price
            if os.getenv('DATABASE_URL'):
                 cursor.execute("""
                    SELECT close FROM prices 
                    WHERE symbol = %s AND date > %s
                    ORDER BY date ASC LIMIT 1
                """, (rec["symbol"], rec["recommendation_date"]))
            else:
                 cursor.execute("""
                    SELECT close FROM prices 
                    WHERE symbol = ? AND date > ?
                    ORDER BY date ASC LIMIT 1
                """, (rec["symbol"], rec["recommendation_date"]))
            
            row = cursor.fetchone()
            
            if row and rec["close_price"] and rec["close_price"] > 0:
                next_close = row["close"]
                return_1d = ((next_close - rec["close_price"]) / rec["close_price"]) * 100
                
                # Was the recommendation correct?
                was_correct = None
                action = rec["action"]
                if action in ("BUY", "UP"):
                    was_correct = return_1d > 0        # Price went up = correct
                elif action in ("SELL", "DOWN"):
                    was_correct = return_1d < 0        # Price went down = correct exit
                elif action == "HOLD":
                    was_correct = return_1d >= -2.0    # Didn't crash = correct hold
                # WATCH: no correctness evaluation
                
                if os.getenv('DATABASE_URL'):
                     cursor.execute("""
                        UPDATE trade_recommendations 
                        SET actual_next_day_return = %s, was_correct = %s
                        WHERE id = %s
                    """, (round(return_1d, 2), was_correct, rec["id"]))
                else:
                     cursor.execute("""
                        UPDATE trade_recommendations 
                        SET actual_next_day_return = ?, was_correct = ?
                        WHERE id = ?
                    """, (round(return_1d, 2), was_correct, rec["id"]))
        
        # Similarly evaluate 5-day returns
        if os.getenv('DATABASE_URL'):
             cursor.execute("""
                SELECT tr.id, tr.symbol, tr.close_price, tr.recommendation_date
                FROM trade_recommendations tr
                WHERE tr.actual_5day_return IS NULL
                AND tr.recommendation_date <= CURRENT_DATE - INTERVAL '7 days'
                AND tr.recommendation_date >= CURRENT_DATE - INTERVAL '30 days'
            """)
        else:
             cursor.execute("""
                SELECT tr.id, tr.symbol, tr.close_price, tr.recommendation_date
                FROM trade_recommendations tr
                WHERE tr.actual_5day_return IS NULL
                AND tr.recommendation_date <= date('now', '-7 days')
                AND tr.recommendation_date >= date('now', '-30 days')
            """)
            
        recs_5d = [dict(row) for row in cursor.fetchall()]
        
        for rec in recs_5d:
            # Get price 5 trading days later
            if os.getenv('DATABASE_URL'):
                 cursor.execute("""
                    SELECT close FROM prices 
                    WHERE symbol = %s AND date > %s
                    ORDER BY date ASC 
                    OFFSET 4 LIMIT 1
                """, (rec["symbol"], rec["recommendation_date"]))
            else:
                 cursor.execute("""
                    SELECT close FROM prices 
                    WHERE symbol = ? AND date > ?
                    ORDER BY date ASC 
                    LIMIT 1 OFFSET 4
                """, (rec["symbol"], rec["recommendation_date"]))
            
            row = cursor.fetchone()
            
            if row and rec["close_price"] and rec["close_price"] > 0:
                close_5d = row["close"]
                return_5d = ((close_5d - rec["close_price"]) / rec["close_price"]) * 100
                
                if os.getenv('DATABASE_URL'):
                    cursor.execute("""
                        UPDATE trade_recommendations SET actual_5day_return = %s WHERE id = %s
                    """, (round(return_5d, 2), rec["id"]))
                else:
                    cursor.execute("""
                        UPDATE trade_recommendations SET actual_5day_return = ? WHERE id = ?
                    """, (round(return_5d, 2), rec["id"]))

if __name__ == "__main__":
    evaluate_past_recommendations()
    print("✅ Trade evaluation complete.")
