"""
Telegram Channel Ingestion Module
Pulls posts from public EGX-focused Telegram channels into the news pipeline.

TARGET CHANNELS:
  @MubasherTA       — Arabic technical analysis, EGX setups, buy/sell calls
  @EgyptianStockk   — EGX market commentary, stock news (Arabic/English mix)

FIRST RUN SETUP:
1. pip install telethon
2. Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env (from https://my.telegram.org/apps)
3. Run: python engines/telegram_reader.py --setup
   This triggers interactive phone number + OTP authentication.
   The .session file is saved to DB automatically after success.
4. All subsequent runs (including GitHub Actions) use the DB session.
5. If session expires: re-run --setup locally, session updates in DB.

ENV VARS:
  TELEGRAM_API_ID    — integer app id from my.telegram.org
  TELEGRAM_API_HASH  — string app hash from my.telegram.org
  TELEGRAM_SESSION   — optional base64 session override (CI/CD injection)
"""

import os
import re
import sys
import json
import base64
import logging
import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Channel config ─────────────────────────────────────────────
CHANNELS = ["MubasherTA", "EgyptianStockk"]

SESSION_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions")
SESSION_NAME = "xmore_telegram"
SESSION_PATH = os.path.join(SESSION_DIR, SESSION_NAME)   # telethon appends .session

# ── EGX ticker whitelist ───────────────────────────────────────
EGX_TICKERS = {
    "COMI", "ETEL", "TMGH", "HRHO", "SKPC", "AMOC", "OCDI", "ORWE",
    "FWRY", "ESRS", "JUFO", "PHAR", "EGTS", "ACGC", "PHDC", "DOMT",
    "OTMT", "EFIH", "CLHO", "SWDY", "ABUK", "RAYA", "SAUD", "CIEB",
    "EGAL", "ARAB", "SPMD", "MNHD", "MOIL", "EKHO",
    # Extended common EGX symbols
    "GBCO", "ISPH", "ADPC", "OIH", "OFH", "ATLC", "IEEC", "AMIA",
    "AMER", "SVCE", "MAAL", "MEPA", "EMFD", "EGBE", "HELI",
}


# ══════════════════════════════════════════════════════════════
# 1. SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def _ensure_session_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)


def load_session_from_db(conn) -> Optional[str]:
    """Load base64 session string from system_config table."""
    try:
        _ensure_system_config_table(conn)
        row = _db_get(conn, "SELECT value FROM system_config WHERE key = 'telegram_session'")
        if row and row.get("value"):
            logger.info("[TELEGRAM:SESSION] Loaded from DB, size %.1fKB",
                        len(row["value"]) / 1024)
            return row["value"]
    except Exception as e:
        logger.warning("[TELEGRAM:SESSION] Could not load from DB: %s", e)
    return None


def save_session_to_db(conn):
    """Read .session file, base64-encode, store in system_config."""
    session_file = SESSION_PATH + ".session"
    if not os.path.exists(session_file):
        logger.warning("[TELEGRAM:SESSION] .session file not found at %s", session_file)
        return
    try:
        with open(session_file, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        _ensure_system_config_table(conn)
        _db_execute(conn, """
            INSERT INTO system_config (key, value, updated_at)
            VALUES ('telegram_session', %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """ if _is_pg(conn) else """
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES ('telegram_session', ?, datetime('now'))
        """, [data])
        logger.info("[TELEGRAM:SESSION] Saved to DB after run, size %.1fKB", len(data) / 1024)
    except Exception as e:
        logger.error("[TELEGRAM:SESSION] Could not save to DB: %s", e)


def _write_session_from_env_or_db(conn):
    """Write .session file from env var or DB before connecting."""
    _ensure_session_dir()
    # Env var takes precedence (CI/CD injection)
    b64 = os.environ.get("TELEGRAM_SESSION")
    if not b64:
        b64 = load_session_from_db(conn)
    if b64:
        session_file = SESSION_PATH + ".session"
        try:
            with open(session_file, "wb") as f:
                f.write(base64.b64decode(b64))
            logger.info("[TELEGRAM:SESSION] Written to disk (%s)", session_file)
        except Exception as e:
            logger.warning("[TELEGRAM:SESSION] Could not write to disk: %s", e)


def _ensure_system_config_table(conn):
    auto_id = "SERIAL" if _is_pg(conn) else "INTEGER"
    tstz    = "TIMESTAMPTZ" if _is_pg(conn) else "TIMESTAMP"
    now_fn  = "NOW()" if _is_pg(conn) else "datetime('now')"
    _db_execute(conn, f"""
        CREATE TABLE IF NOT EXISTS system_config (
            key        VARCHAR(100) PRIMARY KEY,
            value      TEXT,
            updated_at {tstz} DEFAULT {now_fn}
        )
    """)


# ══════════════════════════════════════════════════════════════
# 2. ARABIC / EGX POST PARSER
# ══════════════════════════════════════════════════════════════

_BULLISH_AR = re.compile(r"صعود|شراء|ارتفاع|اختراق|فرصة|مستهدف|ايجابي|إيجابي|تحسن")
_BEARISH_AR = re.compile(r"هبوط|بيع|انخفاض|كسر|تراجع|ضغط|سلبي|ضعف|تصحيح")
_BULLISH_EN = re.compile(r"\b(buy|bullish|breakout|upside|long|support)\b", re.IGNORECASE)
_BEARISH_EN = re.compile(r"\b(sell|bearish|breakdown|downside|short|resistance)\b", re.IGNORECASE)

_PRICE_PAT   = re.compile(r"(\d{1,5}(?:[.,]\d{1,3})?)\s*(?:EGP|جنيه|ج)?")
_ENTRY_PAT   = re.compile(r"(?:دخول|entry|enter)[^\d]*(\d{1,5}(?:[.,]\d{1,3})?)", re.IGNORECASE)
_TARGET_PAT  = re.compile(r"(?:هدف|target|tp)[^\d]*(\d{1,5}(?:[.,]\d{1,3})?)", re.IGNORECASE)
_STOP_PAT    = re.compile(r"(?:وقف|stop|sl)[^\d]*(\d{1,5}(?:[.,]\d{1,3})?)", re.IGNORECASE)
_TICKER_PAT  = re.compile(r"\b([A-Z]{3,5})\b")
_ARABIC_PAT  = re.compile(r"[\u0600-\u06FF]")


def _parse_price(m) -> Optional[float]:
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def parse_egx_post(text: str) -> dict:
    """Extract structured fields from raw Arabic/English EGX post text."""
    if not text:
        return {}

    # Language detection
    arabic_chars = len(_ARABIC_PAT.findall(text))
    ratio = arabic_chars / max(len(text), 1)
    if ratio > 0.4:
        language = "ar"
    elif ratio > 0.1:
        language = "mixed"
    else:
        language = "en"

    # Direction
    bull_score = len(_BULLISH_AR.findall(text)) + len(_BULLISH_EN.findall(text))
    bear_score = len(_BEARISH_AR.findall(text)) + len(_BEARISH_EN.findall(text))
    if bull_score > bear_score:
        direction = "BULLISH"
    elif bear_score > bull_score:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    # Tickers
    raw_tickers = _TICKER_PAT.findall(text)
    tickers = [t for t in raw_tickers if t in EGX_TICKERS]

    # Prices
    entry_price  = _parse_price(_ENTRY_PAT.search(text))
    target_price = _parse_price(_TARGET_PAT.search(text))
    stop_price   = _parse_price(_STOP_PAT.search(text))
    has_price_target = bool(_PRICE_PAT.search(text))

    # Post type
    if entry_price and target_price and stop_price:
        post_type = "SIGNAL"
    elif tickers or (len(text) < 400 and has_price_target):
        post_type = "NEWS"
    else:
        post_type = "COMMENTARY"

    return {
        "tickers":         tickers,
        "direction":       direction,
        "has_price_target": has_price_target,
        "entry_price":     entry_price,
        "target_price":    target_price,
        "stop_price":      stop_price,
        "post_type":       post_type,
        "language":        language,
    }


# ══════════════════════════════════════════════════════════════
# 3. CHANNEL FETCHER (async)
# ══════════════════════════════════════════════════════════════

async def fetch_channel_posts(client, channel: str, hours_back: int = 25) -> list:
    """Pull posts from the last hours_back hours from a public channel."""
    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
    posts = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)

    try:
        async for message in client.iter_messages(channel, reverse=False):
            try:
                if not message.date:
                    continue
                msg_date = message.date
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                if msg_date < cutoff:
                    break
                text = (message.text or "").strip()
                if not text:
                    continue
                posts.append({
                    "source":       f"telegram_{channel}",
                    "channel":      channel,
                    "message_id":   message.id,
                    "text":         text,
                    "url":          f"https://t.me/{channel}/{message.id}",
                    "published_at": msg_date.isoformat(),
                    "views":        message.views or 0,
                    "forwards":     message.forwards or 0,
                    "has_media":    message.media is not None,
                    "raw_json":     json.dumps({
                        "id": message.id,
                        "date": msg_date.isoformat(),
                        "views": message.views,
                    }),
                })
            except Exception as e:
                logger.warning("[TELEGRAM:%s] Skipping message %s: %s",
                               channel, getattr(message, "id", "?"), e)
    except Exception as e:
        logger.error("[TELEGRAM:%s] iter_messages error: %s", channel, e)

    return posts


# ══════════════════════════════════════════════════════════════
# 4. DATABASE INSERTION
# ══════════════════════════════════════════════════════════════

def _ensure_news_columns(conn):
    """Safely add Telegram-specific columns to the news table."""
    pg = _is_pg(conn)
    if pg:
        extra_cols = [
            ("ticker_mentions",  "TEXT[]"),
            ("direction",        "VARCHAR(10)"),
            ("post_type",        "VARCHAR(15)"),
            ("entry_price",      "NUMERIC(10,2)"),
            ("target_price",     "NUMERIC(10,2)"),
            ("stop_price",       "NUMERIC(10,2)"),
            ("views",            "INTEGER DEFAULT 0"),
            ("forwards",         "INTEGER DEFAULT 0"),
            ("has_media",        "BOOLEAN DEFAULT FALSE"),
        ]
        for col, typedef in extra_cols:
            try:
                _db_execute(conn, f"ALTER TABLE news ADD COLUMN IF NOT EXISTS {col} {typedef}")
            except Exception:
                pass
    else:
        # SQLite: try adding columns one by one (IF NOT EXISTS not supported)
        extra_cols = [
            ("ticker_mentions",  "TEXT"),
            ("direction",        "TEXT"),
            ("post_type",        "TEXT"),
            ("entry_price",      "REAL"),
            ("target_price",     "REAL"),
            ("stop_price",       "REAL"),
            ("views",            "INTEGER DEFAULT 0"),
            ("forwards",         "INTEGER DEFAULT 0"),
            ("has_media",        "INTEGER DEFAULT 0"),
        ]
        for col, typedef in extra_cols:
            try:
                _db_execute(conn, f"ALTER TABLE news ADD COLUMN {col} {typedef}")
            except Exception:
                pass


async def insert_posts(conn, posts: list) -> int:
    """Parse and insert posts into news table. Returns count inserted."""
    if not posts:
        return 0
    _ensure_news_columns(conn)
    pg = _is_pg(conn)

    if pg:
        sql = """
            INSERT INTO news
                (source, headline, url, published_at,
                 ticker_mentions, direction, post_type,
                 entry_price, target_price, stop_price,
                 views, forwards, has_media, raw_json)
            VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s,%s)
            ON CONFLICT (source, url) DO NOTHING
        """
    else:
        sql = """
            INSERT OR IGNORE INTO news
                (source, headline, url, published_at,
                 ticker_mentions, direction, post_type,
                 entry_price, target_price, stop_price,
                 views, forwards, has_media, raw_json)
            VALUES (?,?,?,?, ?,?,?, ?,?,?, ?,?,?,?)
        """

    inserted = 0
    for post in posts:
        try:
            parsed = parse_egx_post(post["text"])
            tickers = parsed.get("tickers", [])
            ticker_val = "{" + ",".join(tickers) + "}" if pg else json.dumps(tickers)

            params = [
                post["source"],
                post["text"][:500],         # headline = first 500 chars
                post["url"],
                post["published_at"],
                ticker_val,
                parsed.get("direction"),
                parsed.get("post_type"),
                parsed.get("entry_price"),
                parsed.get("target_price"),
                parsed.get("stop_price"),
                post.get("views", 0),
                post.get("forwards", 0),
                1 if post.get("has_media") else 0,
                post.get("raw_json", "{}"),
            ]
            cur_inserted = _db_execute_rowcount(conn, sql, params)
            inserted += cur_inserted
        except Exception as e:
            logger.error("[TELEGRAM] DB insert error for %s: %s", post.get("url"), e)

    return inserted


# ══════════════════════════════════════════════════════════════
# 5. MAIN PIPELINE
# ══════════════════════════════════════════════════════════════

def run_telegram_pipeline(db_conn, hours_back: int = 25):
    """
    Synchronous entry point called from run_agents.py.
    Handles session load/save, fetches both channels, inserts to DB.
    Non-fatal: any Telegram error is logged and swallowed.
    """
    api_id   = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        logger.info("[TELEGRAM] TELEGRAM_API_ID/HASH not set — skipping Telegram ingestion")
        return

    try:
        api_id = int(api_id)
    except ValueError:
        logger.error("[TELEGRAM] TELEGRAM_API_ID must be an integer — skipping")
        return

    async def _run():
        try:
            from telethon import TelegramClient
            from telethon.errors import (
                FloodWaitError, ChannelPrivateError, SessionExpiredError
            )
        except ImportError:
            logger.warning("[TELEGRAM] telethon not installed (pip install telethon) — skipping")
            return

        _write_session_from_env_or_db(db_conn)

        try:
            async with TelegramClient(SESSION_PATH, api_id, api_hash) as client:
                for channel in CHANNELS:
                    try:
                        posts = await fetch_channel_posts(client, channel, hours_back)
                        inserted = await insert_posts(db_conn, posts)
                        signal_count = sum(1 for p in posts
                                           if parse_egx_post(p["text"]).get("post_type") == "SIGNAL")
                        logger.info("[TELEGRAM:%s] Fetched %d posts, %d new, %d SIGNAL type",
                                    channel, len(posts), inserted, signal_count)
                    except ChannelPrivateError:
                        logger.warning("[TELEGRAM:%s] Channel is private — skipping", channel)
                    except FloodWaitError as e:
                        wait = e.seconds + 5
                        logger.warning("[TELEGRAM:%s] FloodWait %ds — retrying once", channel, wait)
                        await asyncio.sleep(wait)
                        try:
                            posts = await fetch_channel_posts(client, channel, hours_back)
                            inserted = await insert_posts(db_conn, posts)
                            logger.info("[TELEGRAM:%s] Retry: %d posts, %d new",
                                        channel, len(posts), inserted)
                        except Exception as retry_err:
                            logger.error("[TELEGRAM:%s] Retry failed: %s", channel, retry_err)
                    except Exception as e:
                        logger.error("[TELEGRAM:%s] Error: %s", channel, e, exc_info=True)

            save_session_to_db(db_conn)

        except SessionExpiredError:
            logger.critical(
                "[TELEGRAM:SESSION] Session expired — re-run 'python engines/telegram_reader.py --setup' "
                "locally to refresh. Skipping Telegram ingestion."
            )
        except Exception as e:
            logger.error("[TELEGRAM] TelegramClient error: %s", e, exc_info=True)

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("[TELEGRAM] Pipeline error (non-fatal): %s", e, exc_info=True)


# ══════════════════════════════════════════════════════════════
# 6. SETUP CLI
# ══════════════════════════════════════════════════════════════

def _setup_session(db_conn):
    """Interactive first-run auth. Saves session to DB."""
    api_id   = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("ERROR: Set TELEGRAM_API_ID and TELEGRAM_API_HASH in your .env first.")
        sys.exit(1)

    async def _auth():
        from telethon import TelegramClient
        _ensure_session_dir()
        print(f"Starting Telegram authentication...")
        print(f"Session will be saved to: {SESSION_PATH}.session")
        async with TelegramClient(SESSION_PATH, int(api_id), api_hash) as client:
            me = await client.get_me()
            print(f"Authenticated as: {me.first_name} (@{me.username})")
        save_session_to_db(db_conn)
        print("Session saved to database. Future runs will use the DB session.")

    asyncio.run(_auth())


# ══════════════════════════════════════════════════════════════
# DB HELPERS
# ══════════════════════════════════════════════════════════════

def _is_pg(conn) -> bool:
    try:
        return 'psycopg2' in (getattr(type(conn), '__module__', '') or '')
    except Exception:
        return False


def _db_get(conn, sql, params=None):
    params = params or []
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    except Exception:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        return dict(zip(cols, row)) if row else None


def _db_execute(conn, sql, params=None):
    params = params or []
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.execute(sql, params)
        conn.commit()


def _db_execute_rowcount(conn, sql, params=None) -> int:
    params = params or []
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.rowcount if cur.rowcount > 0 else 0
    except Exception:
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount if cur.rowcount > 0 else 0
        except Exception:
            return 0


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="Xmore Telegram ingestion")
    parser.add_argument("--setup",      action="store_true", help="Interactive first-run auth")
    parser.add_argument("--hours-back", type=int, default=25, help="Hours of history to fetch")
    parser.add_argument("--channel",    type=str, default=None, help="Single channel to test")
    args = parser.parse_args()

    # Connect to DB
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        conn = psycopg2.connect(db_url)
    else:
        import sqlite3
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(__file__)), "stocks.db"))

    if args.setup:
        _setup_session(conn)
    else:
        if args.channel:
            CHANNELS[:] = [args.channel]
        run_telegram_pipeline(conn, hours_back=args.hours_back)
