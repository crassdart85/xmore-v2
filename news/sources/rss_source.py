"""
news/sources/rss_source.py — RSS/Atom feed connector.

Fetches articles from an RSS feed, extracts full article body via trafilatura
(with a requests+BeautifulSoup fallback), and returns RawArticle objects.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Optional

from news.models import MarketTag, RawArticle
from news.sources.base import BaseNewsSource

logger = logging.getLogger(__name__)


class RSSNewsSource(BaseNewsSource):
    def __init__(
        self,
        name: str,
        feed_url: str,
        market_tag: MarketTag = MarketTag.UNKNOWN,
        language: str = "en",
        fetch_interval_minutes: int = 15,
    ) -> None:
        self.name = name
        self.feed_url = feed_url
        self.market_tag = market_tag
        self.language = language
        self.fetch_interval_minutes = fetch_interval_minutes
        self._last_fetch_time: Optional[datetime] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_latest(self) -> List[RawArticle]:
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed — skipping RSS source %s", self.name)
            return []

        try:
            feed = feedparser.parse(self.feed_url)
        except Exception as exc:
            logger.error("[%s] feedparser failed: %s", self.name, exc)
            return []

        articles: List[RawArticle] = []
        for entry in feed.entries:
            published_at = self._parse_date(entry)
            if self._last_fetch_time and published_at <= self._last_fetch_time:
                continue

            url = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not title or not url:
                continue

            body = self._extract_body(url)
            if not body or len(body) < 80:
                body = entry.get("summary", "") or entry.get("description", "")

            if not body:
                continue

            content_hash = hashlib.sha256(
                (title + body[:500]).encode("utf-8", errors="replace")
            ).hexdigest()

            articles.append(RawArticle(
                source_name=self.name,
                source_url=self.feed_url,
                title=title,
                body=body,
                published_at=published_at,
                language=self.language,
                url=url,
                content_hash=content_hash,
                market_tag=self.market_tag,
            ))

        self._last_fetch_time = datetime.now(timezone.utc)
        logger.info("[%s] Fetched %d articles", self.name, len(articles))
        return articles

    def health_check(self) -> bool:
        try:
            import feedparser
            feed = feedparser.parse(self.feed_url)
            return len(feed.entries) > 0
        except Exception:
            return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_body(self, url: str) -> str:
        """Try trafilatura first, fall back to requests+BS4."""
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    return text
        except Exception:
            pass

        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, timeout=10, headers={"User-Agent": "XmoreNewsBot/2.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove noise tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            paragraphs = soup.find_all("p")
            return " ".join(p.get_text(" ", strip=True) for p in paragraphs if p.get_text(strip=True))
        except Exception:
            return ""

    def _parse_date(self, entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        return datetime.now(timezone.utc)
