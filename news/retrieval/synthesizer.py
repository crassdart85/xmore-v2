"""
news/retrieval/synthesizer.py — Gemini-powered answer synthesis for Use Case 1.

Receives the top-k retrieved chunks (already ranked by recency + similarity)
and generates an institutional-grade answer via Gemini 2.0 Flash.

The prompt engineering prioritises:
  - Precision: quantify whenever possible (bps, %, dates)
  - Source citation: every factual claim must cite a chunk source
  - Recency awareness: flag stale context explicitly (>48h for market queries)
  - No hallucination: "I cannot determine from the retrieved context" is correct
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the analytical intelligence layer of Xmore v2, an institutional \
quantitative risk platform serving portfolio managers and risk teams on the \
Egyptian Exchange (EGX) and regional emerging markets.

Your role: synthesise retrieved news and document chunks into concise, \
analytically precise answers for sophisticated professionals.

Rules:
- Answer ONLY from the provided context. Do not use general knowledge.
- Quantify wherever possible: basis points, percentages, exact dates.
- Cite the source name and date for each factual claim in brackets, e.g. [Enterprise.press, 2026-03-01].
- If context older than 48 hours is the only relevant source, flag this explicitly.
- If the retrieved context is insufficient, say: "Insufficient context to answer reliably."
- Keep answers concise (4-8 sentences for most queries).
- Do not pad with generic disclaimers or caveats not warranted by the data."""


def synthesize(
    question: str,
    retrieved_chunks: List[dict],
    portfolio_assets: Optional[List[str]] = None,
    language: str = "en",
) -> dict:
    """
    Generate an institutional answer from retrieved news chunks.

    Args:
        question:          User's natural language question.
        retrieved_chunks:  Output from retriever.retrieve_news_chunks() or retrieve_combined().
        portfolio_assets:  Optional list of ticker symbols for personalised answers.
        language:          "en" or "ar" (answer language hint).

    Returns:
        dict with keys: answer, sources, question, context_age_hours.
    """
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    if not retrieved_chunks:
        return {
            "answer": "No relevant news found for your query in the last 7 days.",
            "sources": [],
            "question": question,
            "context_age_hours": None,
        }

    # Build context block
    context_lines = []
    now = datetime.now(timezone.utc)
    oldest_age_hours = 0.0

    for i, r in enumerate(retrieved_chunks, 1):
        pub_str = r.get("published_at") or "unknown date"
        # Compute age for staleness warning
        try:
            if pub_str and pub_str != "unknown date":
                pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                age_h = (now - pub_dt).total_seconds() / 3600
                oldest_age_hours = max(oldest_age_hours, age_h)
        except Exception:
            pass

        content_preview = r.get("content", "")[:500]
        context_lines.append(
            f"[{i}] SOURCE: {r.get('source_name', 'Unknown')} | "
            f"DATE: {pub_str[:10]} | TYPE: {r.get('event_type', 'GENERAL')}\n"
            f"HEADLINE: {r.get('title', '')}\n"
            f"CONTENT: {content_preview}"
        )

    context_block = "\n\n---\n\n".join(context_lines)

    # Portfolio personalisation block
    portfolio_block = ""
    if portfolio_assets:
        portfolio_block = f"\nPORTFOLIO CONTEXT: The user holds positions in: {', '.join(portfolio_assets)}.\n"

    lang_hint = "\nRespond in Arabic." if language == "ar" else ""

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"{portfolio_block}"
        f"RETRIEVED CONTEXT (ranked by relevance × recency):\n{context_block}\n\n"
        f"USER QUERY: {question}{lang_hint}\n\n"
        "Synthesise a precise, institutional-grade answer based strictly on the context above."
    )

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        answer_text = result.text.strip()
    except Exception as exc:
        logger.error("Synthesis API call failed: %s", exc)
        answer_text = f"Synthesis error: {exc}"

    sources = [
        {
            "source_name":   r.get("source_name"),
            "title":         r.get("title"),
            "published_at":  r.get("published_at"),
            "event_type":    r.get("event_type"),
            "relevance_score": round(r.get("final_score", 0.0), 4),
        }
        for r in retrieved_chunks
    ]

    return {
        "answer":              answer_text,
        "sources":             sources,
        "question":            question,
        "context_age_hours":   round(oldest_age_hours, 1),
    }
