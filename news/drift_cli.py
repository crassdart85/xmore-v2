"""
news/drift_cli.py — CLI for Node.js to query drift adjustment status.

Called by Node.js via child_process.spawn:
    python news/drift_cli.py '{"ticker":"COMI.CA"}'
    python news/drift_cli.py '{"recent":true,"limit":20}'
    python news/drift_cli.py '{"verify":"adjustment-uuid-here"}'

Outputs a single JSON object to stdout.
"""

from __future__ import annotations

import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)

    try:
        if "verify" in args:
            from news.drift.audit_log import AuditLog
            ok = AuditLog().verify_integrity(args["verify"])
            print(json.dumps({"ok": True, "integrity_ok": ok}))

        elif args.get("recent"):
            from news.drift.audit_log import AuditLog
            limit = int(args.get("limit", 50))
            rows = AuditLog().get_recent_adjustments(limit=limit)
            print(json.dumps({"ok": True, "adjustments": rows}))

        elif "ticker" in args:
            from news.drift.adjustment_engine import get_drift_engine
            engine = get_drift_engine()
            summary = engine.get_adjustment_summary(args["ticker"].upper())
            print(json.dumps({"ok": True, **summary}))

        else:
            print(json.dumps({"ok": False, "error": "Specify 'ticker', 'recent', or 'verify'"}))

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
