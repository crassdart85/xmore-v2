"""
rag/retriever.py — Cosine similarity retrieval from rag_chunks.

Used by both the Python side (gemini_agent.py / run_agents.py)
and exposed via the Node.js RAG routes through a subprocess call.
"""

import os
import sys
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection, _adapt_sql


def cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two equal-length float lists."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_top_chunks(
    question_embedding: list,
    source_type: str = 'market_report',
    top_k: int = 5
) -> list[dict]:
    """
    Load all rag_chunks for source_type, rank by cosine similarity to question_embedding.

    Returns list of top_k dicts:
        {source_id, chunk_index, chunk_text, similarity}
    sorted descending by similarity.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _adapt_sql("""
                SELECT source_id, chunk_index, chunk_text, embedding
                FROM rag_chunks
                WHERE source_type = ? AND embedding IS NOT NULL
            """),
            (source_type,)
        )
        rows = cursor.fetchall()

    scored = []
    for row in rows:
        r = dict(row) if hasattr(row, 'keys') else {
            "source_id": row[0], "chunk_index": row[1],
            "chunk_text": row[2], "embedding": row[3]
        }
        try:
            emb = json.loads(r["embedding"])
            sim = cosine_similarity(question_embedding, emb)
            scored.append({
                "source_id": r["source_id"],
                "chunk_index": r["chunk_index"],
                "chunk_text": r["chunk_text"],
                "similarity": round(sim, 4),
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]


def embed_query(text: str) -> list[float]:
    """Embed a query string using Gemini text-embedding-004."""
    api_key = os.getenv('GOOGLE_API_KEY', '')
    if not api_key:
        raise RuntimeError('GOOGLE_API_KEY not set')
    from google import genai
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(model='text-embedding-004', contents=text)
    return result.embeddings[0].values


def retrieve_for_query(question: str, source_type: str = 'market_report', top_k: int = 5) -> list[dict]:
    """Convenience: embed question then retrieve top chunks. Returns same format as get_top_chunks."""
    embedding = embed_query(question)
    return get_top_chunks(embedding, source_type=source_type, top_k=top_k)


# ── CLI: called by Node.js via child_process.spawn ──────────────────────────
# Usage: python rag/retriever.py '{"question": "...", "source_type": "market_report", "top_k": 5}'
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print(json.dumps({"error": "No arguments provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
        question = args.get("question", "")
        source_type = args.get("source_type", "market_report")
        top_k = int(args.get("top_k", 5))

        chunks = retrieve_for_query(question, source_type=source_type, top_k=top_k)
        print(json.dumps({"ok": True, "chunks": chunks}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
