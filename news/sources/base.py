"""
news/sources/base.py — Abstract base class for all news source connectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from news.models import RawArticle


class BaseNewsSource(ABC):
    """All source connectors must implement fetch_latest() and health_check()."""

    name: str
    market_tag: str
    language: str
    fetch_interval_minutes: int = 15

    @abstractmethod
    def fetch_latest(self) -> List[RawArticle]:
        """Fetch articles published since last successful fetch."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Returns True if source is reachable and returning valid data."""
        ...
