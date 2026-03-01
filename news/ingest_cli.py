"""
news/ingest_cli.py — CLI entrypoint for manual / CI ingestion.

Usage:
    python news/ingest_cli.py                    # Full cycle (all sources)
    python news/ingest_cli.py --source "IMF News"  # Single source by name
    python news/ingest_cli.py --drift-check COMI.CA  # Print current drift adjustments

Called by CI/CD (scheduled-tasks.yml) and admin panel.
Outputs a JSON summary to stdout. Logging to stderr.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s %(levelname)s %(message)s")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    parser = argparse.ArgumentParser(description="Xmore News Ingestion CLI")
    parser.add_argument("--source", help="Ingest only this source name")
    parser.add_argument("--drift-check", metavar="TICKER", help="Print drift adjustments for a ticker and exit")
    args = parser.parse_args()

    if args.drift_check:
        from news.drift.adjustment_engine import get_drift_engine
        engine = get_drift_engine()
        summary = engine.get_adjustment_summary(args.drift_check.upper())
        print(json.dumps(summary, indent=2))
        return

    from news.sources.registry import ALL_SOURCES
    from news.pipeline.ingestion import NewsIngestionPipeline
    from news.pipeline.deduplicator import Deduplicator
    from news.pipeline.chunker import ArticleChunker
    from news.pipeline.embedder import ChunkEmbedder
    from news.classifier.event_classifier import EventClassifier
    from news.classifier.asset_mapper import AssetMapper
    from news.drift.adjustment_engine import get_drift_engine

    sources = ALL_SOURCES
    if args.source:
        sources = [s for s in ALL_SOURCES if s.name.lower() == args.source.lower()]
        if not sources:
            print(json.dumps({"ok": False, "error": f"Source not found: {args.source}"}))
            sys.exit(1)

    drift_engine = get_drift_engine()
    pipeline = NewsIngestionPipeline(
        sources=sources,
        deduplicator=Deduplicator(),
        chunker=ArticleChunker(),
        classifier=EventClassifier(),
        asset_mapper=AssetMapper(),
        embedder=ChunkEmbedder(),
        drift_trigger_callback=drift_engine.process_chunk,
    )

    summary = pipeline.run_cycle()
    print(json.dumps({"ok": True, **summary}))


if __name__ == "__main__":
    main()
