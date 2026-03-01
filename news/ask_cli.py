"""
news/ask_cli.py — CLI entrypoint for the news Q&A pipeline.

Called by Node.js via child_process.spawn:
    python news/ask_cli.py '{"question":"...","market":"EGX","portfolio":["COMI.CA"]}'

Outputs a single JSON object to stdout. All logging goes to stderr.
"""

from __future__ import annotations

import json
import logging
import os
import sys

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

# Project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"JSON parse error: {exc}"}))
        sys.exit(1)

    question = args.get("question", "").strip()
    if not question:
        print(json.dumps({"ok": False, "error": "question is required"}))
        sys.exit(1)

    market_tag  = args.get("market")       # "EGX" | "TASI" | "MACRO" | None
    portfolio   = args.get("portfolio", [])
    language    = args.get("language", "en")
    top_k       = int(args.get("top_k", 8))
    max_age_h   = float(args.get("max_age_hours", 168))
    source_mode = args.get("source_mode", "news")  # "news" | "combined"

    try:
        if source_mode == "combined":
            from news.retrieval.retriever import retrieve_combined
            chunks = retrieve_combined(
                question,
                market_tag=market_tag,
                top_k=top_k,
                max_news_age_hours=max_age_h,
            )
        else:
            from news.retrieval.retriever import retrieve_news_chunks
            chunks = retrieve_news_chunks(
                question,
                market_tag=market_tag,
                top_k=top_k,
                max_age_hours=max_age_h,
            )

        from news.retrieval.synthesizer import synthesize
        result = synthesize(
            question=question,
            retrieved_chunks=chunks,
            portfolio_assets=portfolio or None,
            language=language,
        )
        print(json.dumps({"ok": True, **result}))

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
