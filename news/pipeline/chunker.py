"""
news/pipeline/chunker.py — Article body chunker.

News articles are typically 200-800 words. We split on word boundaries
with overlap, prepending the title to every chunk for semantic coherence.
The title prepend is critical for retrieval: a chunk about a CBE rate
decision mid-article should still match "CBE interest rate" queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from news.models import MarketTag, EventType, DriftDirection, ProcessedChunk, RawArticle


class ArticleChunker:
    """
    Splits article body into overlapping word-level chunks.
    Each chunk is a ProcessedChunk with classification fields left at defaults
    (they are filled in by EventClassifier and AssetMapper downstream).
    """

    def __init__(self, chunk_words: int = 300, overlap_words: int = 60) -> None:
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words

    def chunk(self, article: RawArticle) -> List[ProcessedChunk]:
        body = (article.body or "").strip()
        if not body:
            return []

        words = body.split()
        chunks: List[ProcessedChunk] = []
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + self.chunk_words, len(words))
            chunk_text = article.title + "\n\n" + " ".join(words[start:end])

            chunks.append(ProcessedChunk(
                chunk_id=str(uuid.uuid4()),
                article_url=article.url,
                source_name=article.source_name,
                title=article.title,
                content=chunk_text,
                published_at=article.published_at,
                ingested_at=datetime.now(timezone.utc),
                language=article.language,
                market_tag=article.market_tag,
                event_type=EventType.GENERAL,       # Filled by classifier
                drift_direction=DriftDirection.UNCERTAIN,
                chunk_index=chunk_index,
            ))

            start += self.chunk_words - self.overlap_words
            chunk_index += 1

        return chunks
