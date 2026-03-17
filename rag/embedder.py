"""
rag/embedder.py — Generic multi-source embedder for Xmore RAG system.

Sources
-------
  market_report   : uploaded PDFs/images in market_reports table
  news_article    : headlines from the main `news` table
  event_intel     : full articles from xmore_event_intel (articles table)

source_meta (JSON stored per chunk)
------------------------------------
  market_report : {"filename": "...", "upload_date": "..."}
  news_article  : {"symbol": "...", "headline": "...", "source": "...", "date": "..."}
  event_intel   : {"title": "...", "source": "...", "published_at": "...", "symbols": [...]}

Usage
-----
    python rag/embedder.py                          # all sources
    python rag/embedder.py --source news_article    # one source
    python rag/embedder.py --source market_report,news_article
    python rag/embedder.py --report-id 5            # specific report (market_report only)
    python rag/embedder.py --days 14                # look-back window for news/events
"""

import os
import sys
import json
import time
import logging
import argparse
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection, _adapt_sql, DATABASE_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

CHUNK_SIZE     = 500    # characters per chunk
CHUNK_OVERLAP  = 50     # overlap between adjacent chunks
EMBED_MODEL    = 'text-embedding-005'
RATE_LIMIT_SLEEP = 0.13  # ~7.5 req/s — under free-tier 10/s

ALL_SOURCES = ('market_report', 'news_article', 'event_intel')


# ── Text helpers ──────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character-level chunks."""
    if not text or not text.strip():
        return []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


# ── Gemini client ─────────────────────────────────────────────────────────────

def _get_client():
    api_key = os.getenv('GOOGLE_API_KEY', '')
    if not api_key:
        raise RuntimeError('GOOGLE_API_KEY not set')
    from google import genai
    return genai.Client(api_key=api_key)


def embed_text(client, text: str) -> list[float]:
    """Embed a single text string → 768-dim float list."""
    result = client.models.embed_content(model=EMBED_MODEL, contents=text)
    return result.embeddings[0].values


# ── DB upsert helper ──────────────────────────────────────────────────────────

def _upsert_chunk(cursor, source_type: str, source_id: int, chunk_index: int,
                  chunk_text: str, embedding: list[float], source_meta: dict):
    """Insert or replace one rag_chunk row (with source_meta)."""
    emb_json  = json.dumps(embedding)
    meta_json = json.dumps(source_meta, ensure_ascii=False)

    if DATABASE_URL:
        # PostgreSQL — also populate embedding_vec for pgvector if column exists
        try:
            vec_str = '[' + ','.join(str(v) for v in embedding) + ']'
            cursor.execute("""
                INSERT INTO rag_chunks
                  (source_type, source_id, chunk_index, chunk_text, embedding, source_meta, embedding_vec)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text    = EXCLUDED.chunk_text,
                              embedding     = EXCLUDED.embedding,
                              source_meta   = EXCLUDED.source_meta,
                              embedding_vec = EXCLUDED.embedding_vec
            """, (source_type, source_id, chunk_index, chunk_text, emb_json, meta_json, vec_str))
        except Exception:
            # Fallback: pgvector column may not exist yet
            cursor.execute("""
                INSERT INTO rag_chunks
                  (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text  = EXCLUDED.chunk_text,
                              embedding   = EXCLUDED.embedding,
                              source_meta = EXCLUDED.source_meta
            """, (source_type, source_id, chunk_index, chunk_text, emb_json, meta_json))
    else:
        cursor.execute("""
            INSERT OR REPLACE INTO rag_chunks
              (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source_type, source_id, chunk_index, chunk_text, emb_json, meta_json))


# ── Source: market_report ─────────────────────────────────────────────────────

def embed_market_reports(client, report_id: int = None) -> int:
    """Embed PDFs/images from market_reports table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if report_id is not None:
            cursor.execute(
                _adapt_sql("SELECT id, filename, extracted_text, upload_date FROM market_reports WHERE id = ?"),
                (report_id,)
            )
        else:
            cursor.execute(_adapt_sql("""
                SELECT mr.id, mr.filename, mr.extracted_text, mr.upload_date
                FROM market_reports mr
                WHERE mr.extracted_text IS NOT NULL AND TRIM(mr.extracted_text) != ''
                  AND mr.id NOT IN (
                      SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = 'market_report'
                  )
                ORDER BY mr.upload_date DESC
            """))
        rows = cursor.fetchall()
        reports = [dict(r) if hasattr(r, 'keys') else
                   {"id": r[0], "filename": r[1], "extracted_text": r[2], "upload_date": str(r[3])}
                   for r in rows]

    if not reports:
        logger.info("[market_report] Nothing new to embed.")
        return 0

    if report_id is not None:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                _adapt_sql("DELETE FROM rag_chunks WHERE source_type = 'market_report' AND source_id = ?"),
                (report_id,)
            )

    total = 0
    for report in reports:
        chunks = _chunk_text(report["extracted_text"] or '')
        if not chunks:
            continue
        logger.info(f"[market_report] {report['filename']}: {len(chunks)} chunks")
        meta = {"filename": report["filename"], "upload_date": str(report.get("upload_date", ""))}
        for idx, text in enumerate(chunks):
            try:
                embedding = embed_text(client, text)
                with get_connection() as conn:
                    _upsert_chunk(conn.cursor(), 'market_report', report["id"], idx, text, embedding, meta)
                total += 1
                time.sleep(RATE_LIMIT_SLEEP)
            except Exception as e:
                logger.error(f"  chunk {idx} failed: {e}")
        logger.info(f"  -> {len(chunks)} chunks done for report {report['id']}")

    logger.info(f"[market_report] {total} chunks embedded across {len(reports)} report(s).")
    return total


# ── Source: news_article ──────────────────────────────────────────────────────

def embed_news_articles(client, days: int = 30, limit: int = 500) -> int:
    """Embed recent headlines from the main `news` table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Fetch news not yet embedded (by id not in rag_chunks)
        cursor.execute(_adapt_sql(f"""
            SELECT n.id, n.symbol, n.date, n.headline, n.source, n.sentiment_label
            FROM news n
            WHERE n.headline IS NOT NULL AND TRIM(n.headline) != ''
              AND n.date >= CURRENT_DATE - INTERVAL {'%s' if DATABASE_URL else '?'} {'DAY' if DATABASE_URL else ''}
              AND n.id NOT IN (
                  SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = 'news_article'
              )
            ORDER BY n.date DESC
            LIMIT {'%s' if DATABASE_URL else '?'}
        """), (days, limit) if DATABASE_URL else (days, limit))
        rows = cursor.fetchall()
        articles = [dict(r) if hasattr(r, 'keys') else
                    {"id": r[0], "symbol": r[1], "date": str(r[2]),
                     "headline": r[3], "source": r[4], "sentiment_label": r[5]}
                    for r in rows]

    if not articles:
        logger.info("[news_article] Nothing new to embed.")
        return 0

    logger.info(f"[news_article] Embedding {len(articles)} headlines...")
    total = 0
    for article in articles:
        # News headlines are short — embed as a single chunk (chunk_index=0)
        text = (
            f"[{article['date']}] {article['headline']}\n"
            f"Symbol: {article['symbol']} | Source: {article.get('source','?')} | "
            f"Sentiment: {article.get('sentiment_label','?')}"
        )
        meta = {
            "symbol":          article["symbol"],
            "headline":        article["headline"],
            "source":          article.get("source") or "",
            "date":            str(article["date"]),
            "sentiment_label": article.get("sentiment_label") or "",
        }
        try:
            embedding = embed_text(client, text)
            with get_connection() as conn:
                _upsert_chunk(conn.cursor(), 'news_article', article["id"], 0, text, embedding, meta)
            total += 1
            time.sleep(RATE_LIMIT_SLEEP)
        except Exception as e:
            logger.error(f"  article {article['id']} failed: {e}")

    logger.info(f"[news_article] {total} headlines embedded.")
    return total


# ── Source: event_intel ───────────────────────────────────────────────────────

def embed_event_intel(client, days: int = 30, limit: int = 200) -> int:
    """
    Embed articles from xmore_event_intel.

    In production (DATABASE_URL set): articles table is in the main PostgreSQL DB.
    Locally: reads from xmore_event_intel.db SQLite file.
    """
    articles = _fetch_event_intel_articles(days, limit)
    if not articles:
        logger.info("[event_intel] Nothing new to embed.")
        return 0

    logger.info(f"[event_intel] Embedding {len(articles)} articles...")
    total = 0
    for article in articles:
        title   = article.get("title") or ""
        content = article.get("content") or ""
        text    = f"{title}\n\n{content[:1200]}"
        if not text.strip():
            continue

        # detected_symbols may be a JSON string or list
        syms = article.get("detected_symbols") or []
        if isinstance(syms, str):
            try:    syms = json.loads(syms)
            except: syms = []

        meta = {
            "title":        title,
            "source":       article.get("source") or "",
            "published_at": str(article.get("published_at") or ""),
            "symbols":      syms,
        }

        chunks = _chunk_text(text) if len(text) > CHUNK_SIZE else [text]
        for idx, chunk in enumerate(chunks):
            try:
                embedding = embed_text(client, chunk)
                with get_connection() as conn:
                    _upsert_chunk(conn.cursor(), 'event_intel', article["id"], idx, chunk, embedding, meta)
                total += 1
                time.sleep(RATE_LIMIT_SLEEP)
            except Exception as e:
                logger.error(f"  event article {article['id']} chunk {idx} failed: {e}")

    logger.info(f"[event_intel] {total} chunks embedded across {len(articles)} article(s).")
    return total


def _fetch_event_intel_articles(days: int, limit: int) -> list[dict]:
    """Fetch un-embedded event intel articles from either main DB or local SQLite."""
    if DATABASE_URL:
        # Production: articles table is in the same PostgreSQL DB
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.id, a.title, a.content, a.published_at, a.source, a.detected_symbols
                    FROM articles a
                    WHERE a.published_at >= NOW() - INTERVAL %s DAY
                      AND a.id NOT IN (
                          SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = 'event_intel'
                      )
                    ORDER BY a.published_at DESC
                    LIMIT %s
                """, (days, limit))
                rows = cursor.fetchall()
                return [dict(r) if hasattr(r, 'keys') else
                        {"id": r[0], "title": r[1], "content": r[2],
                         "published_at": str(r[3]), "source": r[4], "detected_symbols": r[5]}
                        for r in rows]
        except Exception as e:
            logger.warning(f"[event_intel] Could not query articles from main DB: {e}")
            return []
    else:
        # Local: read from xmore_event_intel.db
        db_path = os.getenv('XMORE_EVENT_DB_PATH', 'xmore_event_intel.db')
        if not os.path.exists(db_path):
            logger.info(f"[event_intel] {db_path} not found — skipping.")
            return []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Get already-embedded source_ids from main DB to avoid re-embedding
            already = set()
            try:
                with get_connection() as mc:
                    mc2 = mc.cursor()
                    mc2.execute("SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = 'event_intel'")
                    already = {r[0] for r in mc2.fetchall()}
            except Exception:
                pass

            cur.execute("""
                SELECT id, title, content, published_at, source, detected_symbols
                FROM articles
                WHERE published_at >= datetime('now', ? || ' days')
                ORDER BY published_at DESC
                LIMIT ?
            """, (f'-{days}', limit))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows if r["id"] not in already]
        except Exception as e:
            logger.warning(f"[event_intel] Could not read {db_path}: {e}")
            return []


# ── Main dispatcher ───────────────────────────────────────────────────────────

def embed_all(sources: list[str] = None, report_id: int = None, days: int = 30) -> dict:
    """Embed one or more source types. Returns {source_type: chunk_count} dict."""
    client  = _get_client()
    sources = sources or list(ALL_SOURCES)
    results = {}

    for src in sources:
        if src == 'market_report':
            results[src] = embed_market_reports(client, report_id=report_id)
        elif src == 'news_article':
            results[src] = embed_news_articles(client, days=days)
        elif src == 'event_intel':
            results[src] = embed_event_intel(client, days=days)
        else:
            logger.warning(f"Unknown source type: {src}")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Embed multi-source data into rag_chunks')
    parser.add_argument('--source', default='all',
                        help='Comma-separated source types, or "all". '
                             f'Choices: {", ".join(ALL_SOURCES)}, all')
    parser.add_argument('--report-id', type=int, default=None,
                        help='Embed a specific market_report ID only')
    parser.add_argument('--days', type=int, default=30,
                        help='Look-back window in days for news_article and event_intel (default: 30)')
    args = parser.parse_args()

    src_list = list(ALL_SOURCES) if args.source == 'all' else [s.strip() for s in args.source.split(',')]
    totals = embed_all(sources=src_list, report_id=args.report_id, days=args.days)
    for src, count in totals.items():
        logger.info(f"  {src}: {count} chunks")
