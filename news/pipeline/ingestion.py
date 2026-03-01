"""
news/pipeline/ingestion.py — Ingestion orchestrator.

Single run_cycle() call:
    1. Fetch articles from all sources
    2. Deduplicate (hash + Jaccard)
    3. Chunk each article
    4. Classify event type + direction
    5. Map affected assets + sectors
    6. Embed with Gemini
    7. Persist to news_rag_chunks
    8. Trigger drift adjustment callback for high-impact events

Called by the APScheduler scheduler (news/scheduler.py) and by the CLI
(news/ingest_cli.py) for manual / CI runs.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from news.models import ProcessedChunk, EventType
from news.sources.base import BaseNewsSource
from news.pipeline.deduplicator import Deduplicator
from news.pipeline.chunker import ArticleChunker
from news.pipeline.embedder import ChunkEmbedder
from news.pipeline.storage import upsert_chunks
from news.classifier.event_classifier import EventClassifier
from news.classifier.asset_mapper import AssetMapper

logger = logging.getLogger(__name__)

# Event types that can trigger a drift adjustment (conservative whitelist)
_DRIFT_TRIGGER_TYPES = {
    EventType.RATE_DECISION,
    EventType.FX_MOVE,
    EventType.EARNINGS_RELEASE,
    EventType.IMF_WORLD_BANK,
    EventType.MACRO_DATA,
}


class NewsIngestionPipeline:
    """
    Orchestrates the full ingestion cycle for all configured news sources.
    """

    def __init__(
        self,
        sources: List[BaseNewsSource],
        deduplicator: Optional[Deduplicator] = None,
        chunker: Optional[ArticleChunker] = None,
        classifier: Optional[EventClassifier] = None,
        asset_mapper: Optional[AssetMapper] = None,
        embedder: Optional[ChunkEmbedder] = None,
        drift_trigger_callback: Optional[Callable[[ProcessedChunk], None]] = None,
    ) -> None:
        self.sources = sources
        self.deduplicator = deduplicator or Deduplicator()
        self.chunker = chunker or ArticleChunker()
        self.classifier = classifier or EventClassifier()
        self.asset_mapper = asset_mapper or AssetMapper()
        self.embedder = embedder or ChunkEmbedder()
        self.drift_trigger_callback = drift_trigger_callback

    def run_cycle(self) -> dict:
        """
        Execute one full ingestion cycle across all sources.
        Returns a summary dict with counts per source.
        """
        summary = {"total_articles": 0, "total_chunks": 0, "sources": {}}

        for source in self.sources:
            source_result = {"articles": 0, "chunks": 0, "error": None}
            try:
                articles = source.fetch_latest()
                source_result["articles"] = len(articles)
                summary["total_articles"] += len(articles)

                chunks_this_source = 0
                for article in articles:
                    if self.deduplicator.is_duplicate(article):
                        continue

                    chunks = self.chunker.chunk(article)
                    if not chunks:
                        continue

                    chunks = self.classifier.classify_batch(chunks)
                    chunks = self.asset_mapper.map_batch(chunks)

                    # Filter out IRRELEVANT before embedding (saves API quota)
                    chunks = [c for c in chunks if c.event_type != EventType.IRRELEVANT]
                    if not chunks:
                        continue

                    chunks = self.embedder.embed_batch(chunks)
                    stored = upsert_chunks(chunks)
                    chunks_this_source += stored
                    summary["total_chunks"] += stored

                    # Trigger drift adjustment for qualifying events
                    if self.drift_trigger_callback:
                        for chunk in chunks:
                            if self._is_drift_relevant(chunk):
                                try:
                                    self.drift_trigger_callback(chunk)
                                except Exception as exc:
                                    logger.error("Drift callback failed: %s", exc)

                source_result["chunks"] = chunks_this_source

            except Exception as exc:
                logger.error("[%s] Ingestion cycle failed: %s", source.name, exc, exc_info=True)
                source_result["error"] = str(exc)

            summary["sources"][source.name] = source_result

        logger.info(
            "Ingestion cycle complete. Articles=%d  Chunks stored=%d",
            summary["total_articles"],
            summary["total_chunks"],
        )
        return summary

    def _is_drift_relevant(self, chunk: ProcessedChunk) -> bool:
        """
        Conservative gate: only trigger drift for first chunk of high-impact events
        with a determined direction and identified asset targets.
        """
        return (
            chunk.event_type in _DRIFT_TRIGGER_TYPES
            and chunk.drift_direction.value not in ("UNCERTAIN", "NEUTRAL")
            and len(chunk.affected_assets) > 0
            and chunk.chunk_index == 0   # Avoid re-triggering on later chunks of same article
        )
