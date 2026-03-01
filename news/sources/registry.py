"""
news/sources/registry.py — Canonical registry of all configured news sources.

Add / remove sources here. The scheduler and ingestion pipeline consume ALL_SOURCES.
RSS feed URLs are verified against public endpoints; some may change over time.
"""

from __future__ import annotations

from news.models import MarketTag
from news.sources.rss_source import RSSNewsSource

# ── EGX / Egypt sources ───────────────────────────────────────────────────────

EGX_SOURCES = [
    RSSNewsSource(
        name="Enterprise.press",
        feed_url="https://enterprise.press/feed/",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=15,
    ),
    RSSNewsSource(
        name="Daily News Egypt",
        feed_url="https://dailynewsegypt.com/feed/",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=15,
    ),
    RSSNewsSource(
        name="Egypt Today Business",
        feed_url="https://www.egypttoday.com/RSS/15",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=20,
    ),
    RSSNewsSource(
        name="Mubasher EGX EN",
        feed_url="http://feeds.mubasher.info/en/EGX/news",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=10,
    ),
    RSSNewsSource(
        name="Mubasher EGX AR",
        feed_url="http://feeds.mubasher.info/ar/EGX/news",
        market_tag=MarketTag.EGX,
        language="ar",
        fetch_interval_minutes=10,
    ),
    # Google News RSS fallbacks — broader Egypt business coverage
    RSSNewsSource(
        name="Google News EGX EN",
        feed_url="https://news.google.com/rss/search?q=EGX+OR+%22Egyptian+Exchange%22+stock&hl=en-US&gl=US&ceid=US:en",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=30,
    ),
    RSSNewsSource(
        name="Google News Egypt AR",
        feed_url="https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%A8%D9%88%D8%B1%D8%B5%D8%A9+%D8%A7%D9%84%D9%85%D8%B5%D8%B1%D9%8A%D8%A9&hl=ar&gl=EG&ceid=EG:ar",
        market_tag=MarketTag.EGX,
        language="ar",
        fetch_interval_minutes=30,
    ),
]

# ── MACRO / Global sources ────────────────────────────────────────────────────

MACRO_SOURCES = [
    RSSNewsSource(
        name="IMF News",
        feed_url="https://www.imf.org/en/News/rss",
        market_tag=MarketTag.MACRO,
        language="en",
        fetch_interval_minutes=60,
    ),
    RSSNewsSource(
        name="Reuters Business",
        feed_url="https://news.google.com/rss/search?q=site:reuters.com+business+OR+markets&hl=en-US&gl=US&ceid=US:en",
        market_tag=MarketTag.MACRO,
        language="en",
        fetch_interval_minutes=15,
    ),
    RSSNewsSource(
        name="Reuters Egypt",
        feed_url="https://news.google.com/rss/search?q=site:reuters.com+egypt+market+OR+EGX&hl=en-US&gl=US&ceid=US:en",
        market_tag=MarketTag.EGX,
        language="en",
        fetch_interval_minutes=20,
    ),
    RSSNewsSource(
        name="Al Arabiya Business",
        feed_url="https://news.google.com/rss/search?q=site:english.alarabiya.net+business&hl=en-US&gl=US&ceid=US:en",
        market_tag=MarketTag.MENA,
        language="en",
        fetch_interval_minutes=20,
    ),
]

# ── Combined registry ─────────────────────────────────────────────────────────

ALL_SOURCES = EGX_SOURCES + MACRO_SOURCES
