"""
news/pipeline/embedder.py — Embedding wrapper using Google Gemini text-embedding-005.

Reuses the same model as the existing rag/embedder.py (768-dim vectors),
keeping the entire Xmore RAG layer on a single embedding model so cosine
similarity comparisons between document chunks and news chunks are valid.

Rate limit: free tier allows ~10 requests/second. We use 0.12s sleep between
calls (matching rag/embedder.py). Batch calls are not yet supported by the
Gemini Embedding API (1 content per request).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Optional

from news.models import ProcessedChunk

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-004"
RATE_LIMIT_SLEEP = 0.12   # ~8 req/s — under the free-tier 10/s limit
MAX_CHARS = 2048           # Gemini embedding input cap (in practice >2048 is truncated)


class ChunkEmbedder:
    """
    Embeds ProcessedChunk.content using Gemini text-embedding-005.
    Sets chunk.embedding in place and returns the modified list.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("GOOGLE_API_KEY not set")
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string. Returns a 768-dim float list."""
        client = self._get_client()
        text = text[:MAX_CHARS]
        result = client.models.embed_content(model=EMBED_MODEL, contents=text)
        return result.embeddings[0].values

    def embed_batch(self, chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
        """
        Embed all chunks in-place. Skips IRRELEVANT chunks (no embedding needed).
        Returns the same list with .embedding populated.
        """
        for chunk in chunks:
            if chunk.event_type.value == "IRRELEVANT":
                continue
            try:
                embedding = self.embed_text(chunk.content)
                chunk.embedding = embedding
                time.sleep(RATE_LIMIT_SLEEP)
            except Exception as exc:
                logger.error("Embed failed for chunk %s: %s", chunk.chunk_id, exc)
        return chunks
