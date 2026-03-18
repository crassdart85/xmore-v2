#!/usr/bin/env python3
"""
Command-line interface for the Screening Engine.

Usage:
    python engines/screening_cli.py --action top-picks [--date YYYY-MM-DD] [--top_n 5]
    python engines/screening_cli.py --action sector-rotation [--date YYYY-MM-DD] [--top_n 3]
    python engines/screening_cli.py --action ranked-signals [--date YYYY-MM-DD] [--limit 30]
    python engines/screening_cli.py --action portfolio \
        --budget 100000 [--risk 5] [--date YYYY-MM-DD]

Outputs JSON to stdout.
"""

import argparse
import json
import sys
import os

# Allow importing from project root when called from web-ui subprocess
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from database import get_connection
from engines.screening_engine import (
    compute_top_picks,
    compute_sector_rotation,
    get_ranked_signals,
    build_portfolio,
)


def main():
    parser = argparse.ArgumentParser(description="Screening Engine CLI")
    parser.add_argument("--action", required=True,
                        choices=["top-picks", "sector-rotation", "ranked-signals", "portfolio"])
    parser.add_argument("--date",   default=None, help="ISO date override (YYYY-MM-DD)")
    parser.add_argument("--top_n",  type=int, default=5)
    parser.add_argument("--limit",  type=int, default=30)
    parser.add_argument("--budget", type=float, default=0.0)
    parser.add_argument("--risk",   type=float, default=5.0)
    args = parser.parse_args()

    try:
        with get_connection() as conn:
            if args.action == "top-picks":
                picks = compute_top_picks(conn, pick_date=args.date, top_n=args.top_n)
                print(json.dumps({"picks": picks}))

            elif args.action == "sector-rotation":
                sectors = compute_sector_rotation(conn, rotation_date=args.date, top_n=args.top_n)
                print(json.dumps({"sectors": sectors}))

            elif args.action == "ranked-signals":
                signals = get_ranked_signals(conn, signal_date=args.date, limit=args.limit)
                print(json.dumps({"signals": signals}))

            elif args.action == "portfolio":
                if args.budget <= 0:
                    print(json.dumps({"error": "--budget must be > 0"}))
                    sys.exit(1)
                portfolio = build_portfolio(
                    conn,
                    budget_egp=args.budget,
                    risk_tolerance_pct=args.risk,
                    signal_date=args.date,
                )
                print(json.dumps(portfolio))

    except Exception as exc:
        # Write error as JSON to stdout so Node.js spawn handler can parse it
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
