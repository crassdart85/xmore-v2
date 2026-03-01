"""
rag/embedder.py — Chunks and embeds market_reports into rag_chunks table.

Usage:
    python rag/embedder.py                  # embed all un-embedded reports
    python rag/embedder.py --report-id 5    # embed one specific report
"""

import os
import sys
import json
import time
import logging
import argparse

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection, _adapt_sql, DATABASE_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

CHUNK_SIZE = 500      # characters per chunk
CHUNK_OVERLAP = 50    # overlap between adjacent chunks
EMBED_MODEL = 'text-embedding-004'
RATE_LIMIT_SLEEP = 0.12  # ~8 req/s, under free-tier 10/s limit


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character-level chunks."""
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def _get_client():
    api_key = os.getenv('GOOGLE_API_KEY', '')
    if not api_key:
        raise RuntimeError('GOOGLE_API_KEY not set')
    from google import genai
    return genai.Client(api_key=api_key)


def embed_text(client, text: str) -> list[float]:
    """Embed a single text chunk using Gemini text-embedding-004. Returns 768-dim float list."""
    result = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return result.embeddings[0].values


def embed_all_reports(report_id: int = None):
    """
    Read market_reports not yet embedded, chunk + embed them, store in rag_chunks.
    If report_id is given, re-embed only that one report (replacing existing chunks).
    """
    client = _get_client()

    with get_connection() as conn:
        cursor = conn.cursor()
        if report_id is not None:
            cursor.execute(
                _adapt_sql("SELECT id, filename, extracted_text FROM market_reports WHERE id = ?"),
                (report_id,)
            )
        else:
            cursor.execute(_adapt_sql("""
                SELECT mr.id, mr.filename, mr.extracted_text
                FROM market_reports mr
                WHERE mr.extracted_text IS NOT NULL AND mr.extracted_text != ''
                  AND mr.id NOT IN (
                      SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = 'market_report'
                  )
                ORDER BY mr.upload_date DESC
            """))
        rows = cursor.fetchall()
        reports = [
            dict(r) if hasattr(r, 'keys') else {"id": r[0], "filename": r[1], "extracted_text": r[2]}
            for r in rows
        ]

    if not reports:
        logger.info("No new reports to embed.")
        return 0

    total_chunks = 0
    logger.info(f"Embedding {len(reports)} report(s)...")

    for report in reports:
        rid = report["id"]
        fname = report["filename"]
        chunks = _chunk_text(report["extracted_text"])
        logger.info(f"  [{rid}] {fname}: {len(chunks)} chunks")

        if report_id is not None:
            # Delete existing chunks for this report before re-embedding
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    _adapt_sql("DELETE FROM rag_chunks WHERE source_type = 'market_report' AND source_id = ?"),
                    (rid,)
                )

        for idx, chunk_text in enumerate(chunks):
            try:
                embedding = embed_text(client, chunk_text)
                embedding_json = json.dumps(embedding)

                with get_connection() as conn:
                    cursor = conn.cursor()
                    if DATABASE_URL:
                        cursor.execute("""
                            INSERT INTO rag_chunks (source_type, source_id, chunk_index, chunk_text, embedding)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (source_type, source_id, chunk_index)
                            DO UPDATE SET chunk_text = EXCLUDED.chunk_text, embedding = EXCLUDED.embedding
                        """, ('market_report', rid, idx, chunk_text, embedding_json))
                    else:
                        cursor.execute("""
                            INSERT OR REPLACE INTO rag_chunks
                              (source_type, source_id, chunk_index, chunk_text, embedding)
                            VALUES (?, ?, ?, ?, ?)
                        """, ('market_report', rid, idx, chunk_text, embedding_json))

                total_chunks += 1
                time.sleep(RATE_LIMIT_SLEEP)

            except Exception as e:
                logger.error(f"    Chunk {idx} failed: {e}")
                continue

        logger.info(f"  -> {len(chunks)} chunks embedded for report {rid}")

    logger.info(f"Done. {total_chunks} total chunks embedded.")
    return total_chunks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Embed market_reports into rag_chunks')
    parser.add_argument('--report-id', type=int, default=None, help='Embed a specific report ID only')
    args = parser.parse_args()
    embed_all_reports(report_id=args.report_id)
