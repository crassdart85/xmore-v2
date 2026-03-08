"""
xmore.egx_etp.backfill
~~~~~~~~~~~~~~~~~~~~~~~
One-off historical backfill script.

Run once to populate the initial EGX ETP universe from live EGX pages.
Subsequent daily runs should use the incremental pipeline.

Usage::

    python -m xmore.egx_etp.backfill

The script is a thin wrapper around ``run_daily(run_type='backfill')``.
It prints a human-readable summary after completion.
"""

from __future__ import annotations

import json
import logging
import sys

# Logging is configured in pipeline; configure a minimal version here in case
# backfill is imported before pipeline.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Run the backfill. Returns 0 on success, 1 on failure."""
    logger.info("=== EGX ETP Backfill starting ===")

    from xmore.egx_etp.pipeline import run_daily

    try:
        summary = run_daily(run_type="backfill")
    except Exception as exc:
        logger.critical("Backfill failed with unhandled exception: %s", exc, exc_info=True)
        return 1

    # Pretty-print summary to stderr for operator visibility
    print("\n" + "=" * 60, file=sys.stderr)
    print("Backfill complete", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Status          : {summary.get('status')}", file=sys.stderr)
    print(f"  Cards found     : {summary.get('cards_found', 0)}", file=sys.stderr)
    print(f"  Products upserted: {summary.get('products_upserted', 0)}", file=sys.stderr)
    print(f"  Holdings rows   : {summary.get('holdings_rows', 0)}", file=sys.stderr)
    print(f"  NAV rows        : {summary.get('nav_rows', 0)}", file=sys.stderr)
    print(f"  Volume rows     : {summary.get('volume_rows', 0)}", file=sys.stderr)
    errors = summary.get("errors", [])
    if errors:
        print(f"  Errors ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
