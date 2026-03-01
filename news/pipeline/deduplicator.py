"""
news/pipeline/deduplicator.py — Two-stage article deduplication.

Stage 1 — Exact hash match (SHA-256 of title + body[:500]).
           Fast, catches identical articles syndicated across sources.

Stage 2 — Title Jaccard similarity.
           Catches rephrased duplicates covering the same event without
           requiring a heavy local embedding model. Uses character n-grams
           for language-agnostic comparison (works for Arabic + English).

The deduplicator also checks the live DB to avoid re-ingesting articles
that were already stored in a previous session.
"""

from __future__ import annotations

import logging
from typing import Optional, Set

from news.models import RawArticle

logger = logging.getLogger(__name__)

# Minimum Jaccard similarity on 5-char shingles to declare semantic duplicate
_JACCARD_THRESHOLD = 0.72
_WINDOW_SIZE = 300   # Keep last N titles in sliding window


def _shingles(text: str, k: int = 5) -> set:
    text = text.lower().strip()
    return {text[i:i + k] for i in range(len(text) - k + 1)} if len(text) >= k else {text}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Deduplicator:
    """
    Stateful per-session deduplicator. Call is_duplicate() before chunking.
    The seen_hashes set is pre-seeded from the DB at construction time.
    """

    def __init__(
        self,
        db_hashes: Optional[Set[str]] = None,
        jaccard_threshold: float = _JACCARD_THRESHOLD,
    ) -> None:
        # Exact hashes already in the DB (content_hash = SHA-256 of title+body[:500])
        self.seen_hashes: Set[str] = db_hashes or set()
        self.jaccard_threshold = jaccard_threshold
        # Sliding window of (shingle_set, title) for the current session
        self._title_window: list[set] = []

    def is_duplicate(self, article: RawArticle) -> bool:
        # Stage 1: exact hash
        if article.content_hash in self.seen_hashes:
            logger.debug("Hash duplicate skipped: %.40s", article.title)
            return True

        # Stage 2: title shingle similarity
        shingles = _shingles(article.title)
        for prev_shingles in self._title_window:
            if _jaccard(shingles, prev_shingles) >= self.jaccard_threshold:
                logger.debug("Semantic duplicate skipped: %.40s", article.title)
                return True

        # Not a duplicate — register
        self.seen_hashes.add(article.content_hash)
        self._title_window.append(shingles)
        if len(self._title_window) > _WINDOW_SIZE:
            self._title_window.pop(0)
        return False
