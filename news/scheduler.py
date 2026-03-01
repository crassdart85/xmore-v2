"""
news/scheduler.py — APScheduler job definitions for the news ingestion pipeline.

Usage:
    python news/scheduler.py             # Start the scheduler (blocking)
    python news/scheduler.py --once      # Run one ingestion cycle and exit

The scheduler is designed to run as a long-lived background process alongside
the Node.js web server (or as a separate Render worker service).

Job schedule (default):
  - Full EGX sources: every 15 minutes during market hours (07:00-15:00 UTC)
  - Macro/IMF sources: every 60 minutes
  - Overnight catch-up: once at 21:00 UTC (after EGX close + US evening news)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from news.sources.registry import ALL_SOURCES
from news.pipeline.ingestion import NewsIngestionPipeline
from news.pipeline.deduplicator import Deduplicator
from news.pipeline.chunker import ArticleChunker
from news.pipeline.embedder import ChunkEmbedder
from news.classifier.event_classifier import EventClassifier
from news.classifier.asset_mapper import AssetMapper
from news.drift.adjustment_engine import get_drift_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _build_pipeline() -> NewsIngestionPipeline:
    drift_engine = get_drift_engine()
    return NewsIngestionPipeline(
        sources=ALL_SOURCES,
        deduplicator=Deduplicator(),
        chunker=ArticleChunker(),
        classifier=EventClassifier(),
        asset_mapper=AssetMapper(),
        embedder=ChunkEmbedder(),
        drift_trigger_callback=drift_engine.process_chunk,
    )


def run_once() -> dict:
    """Execute a single ingestion cycle and return the summary."""
    pipeline = _build_pipeline()
    logger.info("Starting single ingestion cycle...")
    summary = pipeline.run_cycle()
    logger.info("Cycle complete: %s", summary)
    return summary


def start_scheduler() -> None:
    """Start APScheduler with configured jobs. Blocks until interrupted."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="UTC")

    # Primary cycle: every 15 minutes
    scheduler.add_job(
        run_once,
        trigger=IntervalTrigger(minutes=15),
        id="news_ingest_primary",
        name="News ingestion (15-min cycle)",
        max_instances=1,
        coalesce=True,
    )

    # Overnight catch-up: 21:00 UTC (covers late US + MENA news after EGX close)
    scheduler.add_job(
        run_once,
        trigger=CronTrigger(hour=21, minute=0),
        id="news_ingest_catchup",
        name="News ingestion (overnight catch-up)",
        max_instances=1,
        coalesce=True,
    )

    logger.info("APScheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Xmore News Ingestion Scheduler")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    if args.once:
        import json
        result = run_once()
        print(json.dumps(result, indent=2))
    else:
        start_scheduler()
