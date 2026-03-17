"""
news/retrieval/retriever.py — Recency-weighted semantic retrieval from news_rag_chunks.

Retrieval score = semantic_similarity * recency_weight * source_weight

recency_weight = exp(-age_days / decay_days)
  - News chunks: decay_days = 2.0 (fast decay — 48h half-life)
  - Document chunks (if queried): decay_days = 14.0

source_weight: official sources (CBE, EGX, IMF) get a 1.2x credibility boost.

All DB access uses the existing get_connection() abstraction for PG/SQLite compat.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

_OFFICIAL_SOURCES = {"CBE Official", "EGX Announcements", "SAMA Official", "IMF News"}
_NEWS_DECAY_DAYS   = 2.0    # news chunks: fast decay
_DOC_DECAY_DAYS    = 14.0   # static document chunks: slow decay


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _recency_weight(published_at: datetime, now: datetime, is_news: bool = True) -> float:
    age_days = (now - published_at).total_seconds() / 86_400
    decay = _NEWS_DECAY_DAYS if is_news else _DOC_DECAY_DAYS
    return math.exp(-age_days / decay)


def _source_weight(source_name: str) -> float:
    return 1.2 if source_name in _OFFICIAL_SOURCES else 1.0


def _embed_query(text: str) -> List[float]:
    """Embed query text using the same Gemini model as the ingestion pipeline."""
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    from google import genai
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(model="text-embedding-005", contents=text)
    return result.embeddings[0].values


def retrieve_news_chunks(
    query: str,
    market_tag: Optional[str] = None,
    event_type: Optional[str] = None,
    top_k: int = 8,
    min_age_hours: float = 0,
    max_age_hours: float = 168,  # 7 days default lookback
) -> List[dict]:
    """
    Embed query, load matching news_rag_chunks from DB, re-rank with recency weight.

    Args:
        query:          Natural language question.
        market_tag:     Optional filter (EGX | TASI | MACRO | MENA).
        event_type:     Optional filter (RATE_DECISION | EARNINGS_RELEASE | ...).
        top_k:          Number of results to return.
        min_age_hours:  Exclude chunks newer than this (usually 0).
        max_age_hours:  Exclude chunks older than this (default 7 days).

    Returns:
        List of result dicts with keys: chunk_id, title, content, source_name,
        published_at, event_type, market_tag, affected_assets, semantic_score,
        recency_weight, final_score.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from database import get_connection, _adapt_sql, DATABASE_URL

    # 1. Embed query
    q_emb = _embed_query(query)

    # 2. Build DB filter clause
    conditions = ["embedding IS NOT NULL"]
    params: list = []
    p = 1

    if market_tag:
        conditions.append(f"market_tag = {'$' + str(p) if DATABASE_URL else '?'}")
        params.append(market_tag)
        p += 1

    if event_type:
        conditions.append(f"event_type = {'$' + str(p) if DATABASE_URL else '?'}")
        params.append(event_type)
        p += 1

    # Age bounds
    now = datetime.now(timezone.utc)
    if max_age_hours > 0:
        cutoff = now.timestamp() - max_age_hours * 3600
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
        conditions.append(f"published_at >= {'$' + str(p) if DATABASE_URL else '?'}")
        params.append(cutoff_iso)
        p += 1

    where = " AND ".join(conditions)
    sql = _adapt_sql(f"""
        SELECT id, title, content, source_name, published_at, event_type,
               market_tag, affected_assets, embedding
        FROM news_rag_chunks
        WHERE {where}
        ORDER BY published_at DESC
        LIMIT 200
    """)

    # 3. Fetch candidates
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    except Exception as exc:
        logger.error("Retrieval DB query failed: %s", exc)
        return []

    if not rows:
        return []

    # 4. Score and re-rank
    results = []
    for row in rows:
        r = dict(row) if hasattr(row, "keys") else {
            "id": row[0], "title": row[1], "content": row[2],
            "source_name": row[3], "published_at": row[4],
            "event_type": row[5], "market_tag": row[6],
            "affected_assets": row[7], "embedding": row[8],
        }
        try:
            emb = json.loads(r["embedding"])
            sem_score = _cosine(q_emb, emb)
            pub_at = r["published_at"]
            if isinstance(pub_at, str):
                pub_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
            rec_weight = _recency_weight(pub_at, now, is_news=True)
            src_weight = _source_weight(r["source_name"])
            final_score = sem_score * rec_weight * src_weight

            results.append({
                "chunk_id":      r["id"],
                "title":         r["title"],
                "content":       r["content"],
                "source_name":   r["source_name"],
                "published_at":  pub_at.isoformat() if hasattr(pub_at, "isoformat") else str(pub_at),
                "event_type":    r["event_type"],
                "market_tag":    r["market_tag"],
                "affected_assets": json.loads(r["affected_assets"]) if isinstance(r["affected_assets"], str) else r["affected_assets"],
                "semantic_score": round(sem_score, 4),
                "recency_weight": round(rec_weight, 4),
                "final_score":   round(final_score, 4),
            })
        except Exception as exc:
            logger.debug("Row scoring failed: %s", exc)
            continue

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:top_k]


def retrieve_combined(
    query: str,
    market_tag: Optional[str] = None,
    top_k: int = 8,
    max_news_age_hours: float = 168,
) -> List[dict]:
    """
    Retrieve from BOTH news_rag_chunks and rag_chunks (market_reports),
    merge and re-rank. Returns up to top_k results with a 'source_type' field.
    """
    news_results = retrieve_news_chunks(
        query, market_tag=market_tag, top_k=top_k,
        max_age_hours=max_news_age_hours
    )
    for r in news_results:
        r["source_type"] = "news"

    # Static doc retrieval (reuse existing rag/retriever pattern)
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from rag.retriever import get_top_chunks, embed_query
        q_emb = embed_query(query)
        doc_chunks = get_top_chunks(q_emb, source_type="market_report", top_k=top_k)
        for d in doc_chunks:
            d["source_type"] = "document"
            d["final_score"] = d.get("similarity", 0.0) * 0.7   # Slight downweight vs fresh news
            d["content"] = d.get("chunk_text", "")
            d["title"] = d.get("filename", "Market Report")
            d["source_name"] = "Market Report"
            d["published_at"] = None
            d["event_type"] = "DOCUMENT"
            d["market_tag"] = "EGX"
        news_results.extend(doc_chunks)
    except Exception:
        pass   # Docs RAG is optional

    news_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    return news_results[:top_k]
