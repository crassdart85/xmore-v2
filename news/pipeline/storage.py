"""
news/pipeline/storage.py — Persists ProcessedChunks to the news_rag_chunks table.

Supports both SQLite (local dev) and PostgreSQL (production) via the
existing database.get_connection() / _adapt_sql() abstraction.
"""

from __future__ import annotations

import json
import logging
from typing import List, Set

from news.models import ProcessedChunk

logger = logging.getLogger(__name__)


def upsert_chunks(chunks: List[ProcessedChunk]) -> int:
    """
    Insert chunks into news_rag_chunks. Duplicate chunk_ids are ignored.
    Returns the number of rows inserted.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from database import get_connection, _adapt_sql, DATABASE_URL

    inserted = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for chunk in chunks:
            if chunk.embedding is None:
                continue   # Don't store un-embedded chunks
            try:
                if DATABASE_URL:
                    sql = """
                        INSERT INTO news_rag_chunks
                            (id, article_url, source_name, title, content, chunk_index,
                             published_at, ingested_at, language, market_tag, event_type,
                             affected_assets, affected_sectors, drift_direction,
                             drift_magnitude_estimate, embedding)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                        ON CONFLICT (id) DO NOTHING
                    """
                else:
                    sql = """
                        INSERT OR IGNORE INTO news_rag_chunks
                            (id, article_url, source_name, title, content, chunk_index,
                             published_at, ingested_at, language, market_tag, event_type,
                             affected_assets, affected_sectors, drift_direction,
                             drift_magnitude_estimate, embedding)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """

                params = (
                    chunk.chunk_id,
                    chunk.article_url,
                    chunk.source_name,
                    chunk.title,
                    chunk.content,
                    chunk.chunk_index,
                    chunk.published_at.isoformat(),
                    chunk.ingested_at.isoformat(),
                    chunk.language,
                    chunk.market_tag.value if hasattr(chunk.market_tag, "value") else str(chunk.market_tag),
                    chunk.event_type.value if hasattr(chunk.event_type, "value") else str(chunk.event_type),
                    json.dumps(chunk.affected_assets),
                    json.dumps(chunk.affected_sectors),
                    chunk.drift_direction.value if hasattr(chunk.drift_direction, "value") else str(chunk.drift_direction),
                    chunk.drift_magnitude_estimate,
                    json.dumps(chunk.embedding),
                )
                cursor.execute(sql, params)
                if cursor.rowcount and cursor.rowcount > 0:
                    inserted += 1
            except Exception as exc:
                logger.warning("Chunk %s insert failed: %s", chunk.chunk_id, exc)
    return inserted


def load_existing_hashes() -> Set[str]:
    """
    Load content_hash values of articles already ingested (from news_rag_chunks).
    Used to pre-seed the Deduplicator at startup.
    We don't store content_hash directly — approximate by checking article_url presence.
    Returns a set of article_urls already stored (used as proxy for dedup).
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from database import get_connection, _adapt_sql

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT article_url FROM news_rag_chunks")
            rows = cursor.fetchall()
        return {
            (r["article_url"] if hasattr(r, "__getitem__") else r[0])
            for r in rows
        }
    except Exception as exc:
        logger.warning("Could not load existing article URLs: %s", exc)
        return set()
