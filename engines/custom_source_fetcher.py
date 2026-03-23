#!/usr/bin/env python3
"""
Custom News Source Fetcher
==========================
Fetches content from admin-configured sources (URLs, RSS feeds, Telegram public
channels, Telegram bot groups) and inserts articles into the news table so the
existing VADER/FinBERT sentiment pipeline can pick them up on the next run.

Called by:
  • Node.js (admin "Fetch Now"):  python engines/custom_source_fetcher.py --source-id N
  • GitHub Actions (daily):       python engines/custom_source_fetcher.py --fetch-all
  • Admin manual text ingest:     python engines/custom_source_fetcher.py --ingest-text '<json>'

All output goes to stdout as newline-delimited JSON so Node.js can parse it.
Logs go to stderr so they don't interfere with stdout JSON.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging (stderr so stdout stays clean for JSON)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [custom_fetcher] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports — graceful fallback if library missing
# ---------------------------------------------------------------------------
try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    logger.warning("feedparser not installed — RSS sources will be skipped")

try:
    from newspaper import Article as NewspaperArticle
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False
    logger.warning("newspaper3k not installed — URL article extraction will use fallback")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.warning("beautifulsoup4 not installed — Telegram public scraping will fail")

try:
    import requests as req_lib
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests not installed — network fetching will fail")

try:
    from langdetect import detect as langdetect_detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

# ---------------------------------------------------------------------------
# DB connection — same pattern used across the project
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

def _get_db_conn():
    """Return a psycopg2 connection (PostgreSQL) or sqlite3 connection."""
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn, True  # (conn, is_postgres)
    else:
        import sqlite3
        # Use the same path as config.DATABASE_PATH (relative to project root)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            sys.path.insert(0, project_root)
            from config import DATABASE_PATH
            db_filename = DATABASE_PATH
        except Exception:
            db_filename = "stocks.db"
        db_path = os.path.join(project_root, db_filename)
        conn = sqlite3.connect(db_path)
        return conn, False

def _ph(n: int, is_postgres: bool) -> str:
    return f"${n}" if is_postgres else "?"

def _adapt(sql: str, is_postgres: bool) -> str:
    if not is_postgres:
        return re.sub(r"\$\d+", "?", sql)
    return sql

def _sanitize_params(params: tuple, is_postgres: bool) -> tuple:
    """Convert datetime objects to ISO strings for SQLite compatibility."""
    if is_postgres:
        return params
    result = []
    for p in params:
        if isinstance(p, datetime):
            result.append(p.isoformat())
        else:
            result.append(p)
    return tuple(result)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")

def detect_language(text: str) -> str:
    """Returns 'ar' or 'en'."""
    if not text:
        return "en"
    ar = len(ARABIC_RE.findall(text))
    en = len(LATIN_RE.findall(text))
    if ar > en:
        return "ar"
    if HAS_LANGDETECT:
        try:
            lang = langdetect_detect(text[:500])
            return "ar" if lang == "ar" else "en"
        except Exception:
            pass
    return "en"

# ---------------------------------------------------------------------------
# Symbol matching — mirrors rss_news_collector.match_article_to_symbols
# ---------------------------------------------------------------------------
# Minimal inline fallback so this module has no hard dependency on rss_news_collector
def _match_to_symbols(text: str, conn, is_postgres: bool) -> List[str]:
    """
    Match text to KSA stock symbols using the Tadawul reference universe.
    Falls back to top liquid Tadawul names for general market news.
    """
    try:
        from rss_news_collector import match_article_to_symbols
        return match_article_to_symbols({"title": text, "summary": ""})
    except Exception:
        pass

    # Inline fallback: scan the KSA reference universe.
    from config.ksa_universe import KSA_TOP50

    symbols: List[str] = []
    text_upper = text.upper()
    text_lower = text.lower()

    try:
        for stock in KSA_TOP50:
            sym = stock["symbol"]
            name_en = stock.get("name_en", "") or ""
            name_ar = stock.get("name_ar", "") or ""
            ticker = sym.split(".")[0].upper()
            if re.search(rf"\b{ticker}\b", text_upper):
                symbols.append(sym)
                continue
            sig_words = [w for w in name_en.upper().split() if len(w) > 4]
            if sig_words and sum(1 for w in sig_words if w in text_upper) >= 1:
                symbols.append(sym)
                continue
            if name_ar and name_ar in text:
                symbols.append(sym)
    except Exception as e:
        logger.warning("Symbol match DB error: %s", e)

    market_kws = [
        "tadawul", "saudi exchange", "saudi market", "riyadh market",
        "السوق السعودي", "تداول", "tasi",
    ]
    if any(kw in text_lower for kw in market_kws):
        symbols.extend(["2222.SR", "2010.SR", "1120.SR", "7010.SR", "1180.SR"])

    return list(set(symbols))

# ---------------------------------------------------------------------------
# Simple sentiment (fallback when VADER/FinBERT not available)
# ---------------------------------------------------------------------------
_POS = ["rise", "gain", "profit", "growth", "surge", "rally", "bull", "high",
        "expand", "dividend", "success", "ارتفاع", "صعود", "ربح", "نمو", "أرباح"]
_NEG = ["fall", "drop", "loss", "decline", "plunge", "crash", "bear", "low",
        "cut", "fail", "debt", "risk", "concern", "انخفاض", "هبوط", "خسارة", "تراجع"]

def _quick_sentiment(text: str) -> Tuple[float, str]:
    tl = text.lower()
    pos = sum(1 for w in _POS if w in tl)
    neg = sum(1 for w in _NEG if w in tl)
    total = pos + neg
    if total == 0:
        return 0.0, "neutral"
    score = round((pos - neg) / total, 3)
    label = "positive" if score > 0.2 else ("negative" if score < -0.2 else "neutral")
    return score, label

# ---------------------------------------------------------------------------
# DB helpers: custom_source_articles + news
# ---------------------------------------------------------------------------
def _article_exists(cur, source_id: int, external_id: str, is_postgres: bool) -> bool:
    sql = _adapt(
        "SELECT 1 FROM custom_source_articles WHERE source_id = $1 AND external_id = $2",
        is_postgres,
    )
    cur.execute(sql, (source_id, external_id))
    return cur.fetchone() is not None

def _insert_article(cur, source_id: int, content: str, content_type: str,
                    original_url: Optional[str], external_id: str,
                    language: str, sentiment_score: float, sentiment_label: str,
                    message_date: Optional[datetime], is_postgres: bool) -> None:
    processed_val = True if is_postgres else 1
    sql = _adapt("""
        INSERT INTO custom_source_articles
            (source_id, content_text, content_type, original_url, external_id,
             language, sentiment_score, sentiment_label, sentiment_processed, message_date)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        ON CONFLICT (source_id, external_id) DO NOTHING
    """, is_postgres)
    params = _sanitize_params((
        source_id, content, content_type, original_url, external_id,
        language, sentiment_score, sentiment_label, processed_val, message_date,
    ), is_postgres)
    cur.execute(sql, params)

def _insert_news(cur, symbol: str, headline: str, source_name: str,
                 url: Optional[str], sentiment_score: float, sentiment_label: str,
                 article_date: datetime, is_postgres: bool) -> None:
    date_str = article_date.strftime("%Y-%m-%d") if article_date else datetime.now().strftime("%Y-%m-%d")
    sql = _adapt("""
        INSERT INTO news (symbol, date, headline, source, url, sentiment_score, sentiment_label)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (symbol, headline, date) DO NOTHING
    """, is_postgres)
    cur.execute(sql, (symbol, date_str, headline[:500], source_name, url, sentiment_score, sentiment_label))
    # Note: article_date is already converted to date_str above — no datetime passed to cursor

def _update_source_fetched(cur, source_id: int, telegram_offset: Optional[int],
                           is_postgres: bool) -> None:
    ts = "NOW()" if is_postgres else "datetime('now')"
    if telegram_offset is not None:
        sql = _adapt(
            f"UPDATE custom_news_sources SET last_fetched_at = {ts}, telegram_offset = $1 WHERE id = $2",
            is_postgres,
        )
        cur.execute(sql, (telegram_offset, source_id))
    else:
        sql = _adapt(
            f"UPDATE custom_news_sources SET last_fetched_at = {ts} WHERE id = $1",
            is_postgres,
        )
        cur.execute(sql, (source_id,))

# ---------------------------------------------------------------------------
# Content fingerprint for dedup of manual/Telegram content with no URL
# ---------------------------------------------------------------------------
def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:32]

# ---------------------------------------------------------------------------
# Fetch strategies
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

def _fetch_url_article(url: str) -> Optional[str]:
    """Extract main article text from a URL using newspaper3k or BS4 fallback."""
    if HAS_NEWSPAPER:
        try:
            art = NewspaperArticle(url)
            art.download()
            art.parse()
            text = art.text.strip()
            if text:
                return f"{art.title}\n\n{text}"
        except Exception as e:
            logger.warning("newspaper3k failed for %s: %s", url, e)

    if HAS_REQUESTS and HAS_BS4:
        try:
            resp = req_lib.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:5000]
        except Exception as e:
            logger.warning("BS4 fallback failed for %s: %s", url, e)
    return None


def _fetch_rss(feed_url: str) -> List[Dict]:
    """Return list of {title, link, summary, published} dicts from RSS/Atom feed."""
    if not HAS_FEEDPARSER:
        return []
    try:
        feed = feedparser.parse(feed_url)
        results = []
        for entry in feed.entries:
            pub = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            else:
                pub = datetime.now(timezone.utc)
            results.append({
                "title": html_lib.unescape(entry.get("title", "")),
                "link": entry.get("link", ""),
                "summary": html_lib.unescape(entry.get("summary", entry.get("description", ""))),
                "published": pub,
            })
        return results
    except Exception as e:
        logger.error("RSS fetch error for %s: %s", feed_url, e)
        return []


def _fetch_telegram_public(channel_url: str) -> List[Dict]:
    """
    Scrape a public Telegram channel via t.me/s/{username}.
    Returns list of {text, external_id, message_date}.
    """
    if not (HAS_REQUESTS and HAS_BS4):
        logger.warning("requests+bs4 required for Telegram public scraping")
        return []

    # Normalise input: accept t.me/channel or just channel name
    channel_url = channel_url.strip().rstrip("/")
    if not channel_url.startswith("http"):
        channel_url = f"https://t.me/{channel_url}"

    # The /s/ path shows a web preview of the last ~30 posts
    if "/s/" not in channel_url:
        parts = channel_url.split("t.me/")
        channel = parts[-1].lstrip("@").split("/")[0]
        preview_url = f"https://t.me/s/{channel}"
    else:
        preview_url = channel_url

    try:
        resp = req_lib.get(preview_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning("Telegram preview returned %s for %s", resp.status_code, preview_url)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        messages = soup.select(".tgme_widget_message")
        results = []
        for msg in messages:
            text_el = msg.select_one(".tgme_widget_message_text")
            if not text_el:
                continue
            text = text_el.get_text(separator=" ", strip=True)
            if not text:
                continue

            # data-post="channelname/12345"
            data_post = msg.get("data-post", "")
            external_id = data_post if data_post else _fingerprint(text)

            # Parse message date
            time_el = msg.select_one("time")
            msg_date = None
            if time_el and time_el.get("datetime"):
                try:
                    msg_date = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append({
                "text": text,
                "external_id": external_id,
                "message_date": msg_date or datetime.now(timezone.utc),
            })
        return results
    except Exception as e:
        logger.error("Telegram public scrape error: %s", e)
        return []


def _fetch_telegram_bot(bot_token: str, offset: int) -> Tuple[List[Dict], int]:
    """
    Fetch messages via the Telegram Bot API getUpdates endpoint.
    Returns (messages, new_offset).
    """
    if not HAS_REQUESTS:
        return [], offset
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = req_lib.get(url, params={"offset": offset, "limit": 100, "timeout": 0},
                           timeout=20)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Bot API error: %s", data.get("description"))
            return [], offset

        updates = data.get("result", [])
        messages = []
        new_offset = offset
        for upd in updates:
            new_offset = max(new_offset, upd["update_id"] + 1)
            msg = upd.get("message") or upd.get("channel_post")
            if not msg:
                continue
            text = msg.get("text") or msg.get("caption") or ""
            text = text.strip()
            if not text:
                continue
            msg_date = datetime.fromtimestamp(msg.get("date", time.time()), tz=timezone.utc)
            messages.append({
                "text": text,
                "external_id": str(upd["update_id"]),
                "message_date": msg_date,
            })
        return messages, new_offset
    except Exception as e:
        logger.error("Telegram Bot API error: %s", e)
        return [], offset

# ---------------------------------------------------------------------------
# Core: process a single source
# ---------------------------------------------------------------------------
def process_source(source: Dict, conn, is_postgres: bool) -> Dict:
    """
    Fetch content from one source and write new articles to DB.
    Returns summary dict.
    """
    source_id = source["id"]
    source_name = source["name"]
    source_type = source["source_type"]
    source_url = source.get("source_url") or ""
    language_pref = source.get("language", "auto")

    articles_fetched = 0
    articles_new = 0
    errors = []

    cur = conn.cursor()

    try:
        if source_type == "rss":
            entries = _fetch_rss(source_url)
            articles_fetched = len(entries)
            for entry in entries:
                content = f"{entry['title']}\n\n{entry['summary']}".strip()
                if not content:
                    continue
                external_id = _fingerprint(entry.get("link") or content)
                if entry.get("link"):
                    external_id = entry["link"]
                if _article_exists(cur, source_id, external_id, is_postgres):
                    continue
                lang = language_pref if language_pref != "auto" else detect_language(content)
                score, label = _quick_sentiment(content)
                _insert_article(cur, source_id, content, "url_article",
                                entry.get("link"), external_id, lang, score, label,
                                entry.get("published"), is_postgres)
                # Match to stocks and write to news table
                symbols = _match_to_symbols(content, conn, is_postgres)
                if not symbols:
                    symbols = ["COMI.CA"]  # fallback: general market
                headline = entry["title"][:500] or content[:200]
                for sym in symbols:
                    _insert_news(cur, sym, headline, source_name,
                                 entry.get("link"), score, label,
                                 entry.get("published") or datetime.now(timezone.utc),
                                 is_postgres)
                articles_new += 1

        elif source_type == "url":
            content = _fetch_url_article(source_url)
            if not content:
                errors.append(f"Could not extract content from {source_url}")
            else:
                articles_fetched = 1
                external_id = source_url
                if not _article_exists(cur, source_id, external_id, is_postgres):
                    lang = language_pref if language_pref != "auto" else detect_language(content)
                    score, label = _quick_sentiment(content)
                    _insert_article(cur, source_id, content, "url_article",
                                    source_url, external_id, lang, score, label,
                                    datetime.now(timezone.utc), is_postgres)
                    symbols = _match_to_symbols(content, conn, is_postgres)
                    if not symbols:
                        symbols = ["COMI.CA"]
                    headline = content.split("\n")[0][:500]
                    for sym in symbols:
                        _insert_news(cur, sym, headline, source_name,
                                     source_url, score, label,
                                     datetime.now(timezone.utc), is_postgres)
                    articles_new = 1

        elif source_type == "telegram_public":
            msgs = _fetch_telegram_public(source_url)
            articles_fetched = len(msgs)
            for m in msgs:
                if _article_exists(cur, source_id, m["external_id"], is_postgres):
                    continue
                lang = language_pref if language_pref != "auto" else detect_language(m["text"])
                score, label = _quick_sentiment(m["text"])
                _insert_article(cur, source_id, m["text"], "text",
                                None, m["external_id"], lang, score, label,
                                m["message_date"], is_postgres)
                symbols = _match_to_symbols(m["text"], conn, is_postgres)
                if not symbols:
                    symbols = ["COMI.CA"]
                for sym in symbols:
                    _insert_news(cur, sym, m["text"][:500], source_name,
                                 None, score, label, m["message_date"], is_postgres)
                articles_new += 1

        elif source_type == "telegram_bot":
            bot_token = source.get("bot_token") or ""
            if not bot_token:
                errors.append("No bot_token configured for this source")
            else:
                offset = int(source.get("telegram_offset") or 0)
                msgs, new_offset = _fetch_telegram_bot(bot_token, offset)
                articles_fetched = len(msgs)
                for m in msgs:
                    if _article_exists(cur, source_id, m["external_id"], is_postgres):
                        continue
                    lang = language_pref if language_pref != "auto" else detect_language(m["text"])
                    score, label = _quick_sentiment(m["text"])
                    _insert_article(cur, source_id, m["text"], "text",
                                    None, m["external_id"], lang, score, label,
                                    m["message_date"], is_postgres)
                    symbols = _match_to_symbols(m["text"], conn, is_postgres)
                    if not symbols:
                        symbols = ["COMI.CA"]
                    for sym in symbols:
                        _insert_news(cur, sym, m["text"][:500], source_name,
                                     None, score, label, m["message_date"], is_postgres)
                    articles_new += 1
                _update_source_fetched(cur, source_id, new_offset, is_postgres)
                conn.commit()
                return {
                    "ok": True, "source_id": source_id, "source_name": source_name,
                    "articles_fetched": articles_fetched, "articles_new": articles_new,
                    "errors": errors,
                }

        elif source_type == "manual":
            # Manual sources are inserted directly by Node.js; nothing to auto-fetch
            pass

        _update_source_fetched(cur, source_id, None, is_postgres)
        conn.commit()

    except Exception as e:
        logger.error("Error processing source %s (%s): %s", source_id, source_name, e)
        errors.append(str(e))
        try:
            conn.rollback()
        except Exception:
            pass

    return {
        "ok": len(errors) == 0,
        "source_id": source_id,
        "source_name": source_name,
        "articles_fetched": articles_fetched,
        "articles_new": articles_new,
        "errors": errors,
    }

# ---------------------------------------------------------------------------
# Manual text ingest (called by Node.js for WhatsApp paste + file upload)
# ---------------------------------------------------------------------------
def ingest_manual_text(payload: Dict) -> Dict:
    """
    Insert manually-provided text into custom_source_articles and news tables.
    payload: {source_id, content, language, content_type}
    """
    conn, is_postgres = _get_db_conn()
    try:
        source_id = int(payload["source_id"])
        content = payload.get("content", "").strip()
        if not content:
            return {"ok": False, "error": "Empty content"}

        content_type = payload.get("content_type", "text")
        lang = payload.get("language") or detect_language(content)
        external_id = _fingerprint(content)

        cur = conn.cursor()

        # Get source name
        sql = _adapt("SELECT name FROM custom_news_sources WHERE id = $1", is_postgres)
        cur.execute(sql, (source_id,))
        row = cur.fetchone()
        source_name = row[0] if row else "WhatsApp"

        if _article_exists(cur, source_id, external_id, is_postgres):
            conn.close()
            return {"ok": True, "articles_new": 0, "message": "Duplicate content — already stored"}

        score, label = _quick_sentiment(content)
        _insert_article(cur, source_id, content, content_type,
                        None, external_id, lang, score, label,
                        datetime.now(timezone.utc), is_postgres)

        symbols = _match_to_symbols(content, conn, is_postgres)
        if not symbols:
            symbols = ["COMI.CA"]
        for sym in symbols:
            _insert_news(cur, sym, content[:500], source_name,
                         None, score, label, datetime.now(timezone.utc), is_postgres)

        conn.commit()
        conn.close()
        return {
            "ok": True,
            "articles_new": 1,
            "symbols_matched": symbols,
            "language": lang,
            "sentiment": label,
        }
    except Exception as e:
        logger.error("ingest_manual_text error: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Fetch single source by ID
# ---------------------------------------------------------------------------
def fetch_single_source(source_id: int) -> Dict:
    conn, is_postgres = _get_db_conn()
    try:
        cur = conn.cursor()
        sql = _adapt("SELECT * FROM custom_news_sources WHERE id = $1", is_postgres)
        cur.execute(sql, (source_id,))
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": f"Source {source_id} not found"}

        cols = [d[0] for d in cur.description]
        source = dict(zip(cols, row))
        result = process_source(source, conn, is_postgres)
        conn.close()
        return result
    except Exception as e:
        logger.error("fetch_single_source error: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Fetch all active sources
# ---------------------------------------------------------------------------
def fetch_all_active_sources() -> List[Dict]:
    conn, is_postgres = _get_db_conn()
    results = []
    try:
        cur = conn.cursor()
        sql = "SELECT * FROM custom_news_sources WHERE is_active = TRUE ORDER BY id"
        if is_postgres:
            cur.execute(sql)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        sources = [dict(zip(cols, r)) for r in rows]
        conn.close()

        for src in sources:
            if src.get("source_type") == "manual":
                continue
            logger.info("Fetching source: %s (%s)", src["name"], src["source_type"])
            conn2, is_postgres2 = _get_db_conn()
            result = process_source(src, conn2, is_postgres2)
            conn2.close()
            results.append(result)
            logger.info("  → fetched=%d new=%d", result["articles_fetched"], result["articles_new"])
    except Exception as e:
        logger.error("fetch_all_active_sources error: %s", e)
        results.append({"ok": False, "error": str(e)})
    return results

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--fetch-all" in args:
        results = fetch_all_active_sources()
        total_fetched = sum(r.get("articles_fetched", 0) for r in results)
        total_new = sum(r.get("articles_new", 0) for r in results)
        print(json.dumps({
            "ok": True,
            "sources_processed": len(results),
            "total_articles_fetched": total_fetched,
            "total_articles_new": total_new,
            "results": results,
        }))

    elif "--source-id" in args:
        idx = args.index("--source-id")
        try:
            sid = int(args[idx + 1])
        except (IndexError, ValueError):
            print(json.dumps({"ok": False, "error": "Invalid --source-id argument"}))
            sys.exit(1)
        result = fetch_single_source(sid)
        print(json.dumps(result))

    elif "--ingest-text" in args:
        idx = args.index("--ingest-text")
        try:
            payload = json.loads(args[idx + 1])
        except (IndexError, json.JSONDecodeError) as e:
            print(json.dumps({"ok": False, "error": f"Invalid --ingest-text JSON: {e}"}))
            sys.exit(1)
        result = ingest_manual_text(payload)
        print(json.dumps(result))

    else:
        print(json.dumps({"ok": False, "error": "Usage: --fetch-all | --source-id N | --ingest-text '{json}'"}))
        sys.exit(1)
