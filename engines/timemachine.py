"""
Time Machine Orchestrator
Called by Node.js via child_process:

    python engines/timemachine.py '{"amount": 50000, "start_date": "2025-06-15"}'

Prints JSON result to stdout. Node.js captures and returns to frontend.
NO DATABASE WRITES — all data stays in Python memory.
"""

import json
import sys
import os
import logging
from datetime import datetime

# Ensure project root is on path so we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timemachine_data import fetch_historical_prices, get_stock_name
from timemachine_signals import generate_signals_for_period
from timemachine_engine import run_simulation

# Configure logging to stderr (stdout is reserved for JSON output)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('timemachine')


def _has_sufficient_history(price_data: dict, start_date: str) -> bool:
    """
    Require any in-range market data.
    This preflight is for data availability only, not signal richness.
    """
    if not price_data:
        return False
    for rows in price_data.values():
        if any(r.get('date', '') >= start_date for r in rows):
            return True
    return False


def main():
    try:
        # Parse input from Node.js
        if len(sys.argv) < 2:
            _error('Missing input argument')
            return

        input_data = json.loads(sys.argv[1])
        amount = float(input_data['amount'])
        start_date = input_data['start_date']
        end_date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"Time Machine: {amount:,.0f} SAR from {start_date} to {end_date}")

        # Validate start date
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        if start_dt >= datetime.now():
            _error(
                'Start date must be in the past.',
                'تاريخ البداية يجب أن يكون في الماضي.'
            )
            return

        two_years_ago = datetime.now().replace(year=datetime.now().year - 2)
        if start_dt < two_years_ago:
            _error(
                'Start date cannot be more than 2 years ago.',
                'تاريخ البداية لا يمكن أن يكون أكثر من سنتين في الماضي.'
            )
            return

        # Step 1: Fetch historical prices (temporary — not saved to DB)
        logger.info("Step 1/3: Fetching historical prices from Yahoo Finance...")
        price_data = fetch_historical_prices(start_date, end_date)

        if not _has_sufficient_history(price_data, start_date):
            _error(
                'Insufficient price data available for this date range. Try a more recent date.',
                'بيانات الأسعار غير كافية لهذه الفترة. جرب تاريخاً أحدث.'
            )
            return

        # Step 2: Generate retroactive signals
        logger.info("Step 2/3: Generating retroactive trading signals...")
        signals = generate_signals_for_period(price_data, start_date, end_date)

        # Do not fail short windows with sparse/zero signals.
        # The engine can still return a valid flat portfolio outcome.

        # Step 3: Run backtest simulation (entirely in-memory)
        logger.info("Step 3/3: Running backtest simulation...")
        result = run_simulation(amount, start_date, signals, price_data,
                                stock_names_fn=get_stock_name)

        # Check if engine returned an error
        if result.get('error'):
            print(json.dumps(result, default=str))
            return

        # Output result as JSON (Node.js captures stdout)
        logger.info("Simulation complete. Sending results.")
        print(json.dumps(result, default=str))

        # Nothing to clean up — all price_data and signals were in-memory only

    except json.JSONDecodeError as e:
        _error(f'Invalid input JSON: {e}')
    except Exception as e:
        logger.exception("Time Machine failed")
        _error(
            'Simulation failed. The market data might be temporarily unavailable. Please try again.',
            'فشلت المحاكاة. بيانات السوق قد تكون غير متاحة مؤقتاً. يرجى المحاولة مرة أخرى.'
        )


def _error(message_en, message_ar=None):
    """Print error JSON to stdout and exit."""
    print(json.dumps({
        'error': True,
        'message_en': message_en,
        'message_ar': message_ar or message_en,
    }))


if __name__ == '__main__':
    main()
