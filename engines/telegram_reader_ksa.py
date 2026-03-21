"""
KSA Telegram Reader — pulls posts from public Saudi stock channels.
Mirrors telegram_reader.py patterns; session stored as 'telegram_session_ksa'.
"""
import asyncio
import base64
import logging
import os
import re
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── KSA Channel config ─────────────────────────────────────────────────────
KSA_CHANNELS = [
    "Argaam",
    "mubasher_sa",
    "SaudiStockMarket",
    "argaamcom",
]

KSA_CHANNEL_WEIGHTS = {
    "Argaam":           0.70,
    "mubasher_sa":      0.65,
    "SaudiStockMarket": 0.40,
    "argaamcom":        0.65,
}

# KSA ticker whitelist — 4-digit numeric codes
from config.ksa_universe import KSA_TOP50
KSA_TICKER_CODES  = {t[0] for t in KSA_TOP50}   # "2222", "1120", ...
KSA_TICKER_SR     = {t[1] for t in KSA_TOP50}    # "2222.SR", ...

# ── Ticker extraction ───────────────────────────────────────────────────────
def _extract_ksa_tickers(text: str) -> list:
    """Extract 4-digit Saudi ticker codes and .SR symbols from text."""
    found = set()
    # Match 4-digit codes (e.g. 2222, 1120)
    for m in re.finditer(r'\b(\d{4})\b', text):
        code = m.group(1)
        if code in KSA_TICKER_CODES:
            # Convert to .SR format
            found.add(f"{code}.SR")
    # Also match explicit .SR symbols
    for m in re.finditer(r'\b(\d{4})\.SR\b', text, re.IGNORECASE):
        found.add(m.group(0).upper())
    return [t for t in found if t in KSA_TICKER_SR]

# ── Direction / post type ────────────────────────────────────────────────────
_BULLISH_PATTERNS = [
    r'\bشراء\b', r'\bارتفاع\b', r'\bصعود\b', r'\bBUY\b', r'\bBULLISH\b',
    r'\bنمو\b', r'\bمكاسب\b', r'\bتوزيعات\b',
]
_BEARISH_PATTERNS = [
    r'\bبيع\b', r'\bانخفاض\b', r'\bهبوط\b', r'\bSELL\b', r'\bBEARISH\b',
    r'\bغرامة\b', r'\bتحقيق\b',
]

def _parse_direction(text: str) -> str:
    bull = sum(1 for p in _BULLISH_PATTERNS if re.search(p, text, re.IGNORECASE))
    bear = sum(1 for p in _BEARISH_PATTERNS if re.search(p, text, re.IGNORECASE))
    if bull > bear:   return "BULLISH"
    if bear > bull:   return "BEARISH"
    return "NEUTRAL"

def _parse_post_type(text: str) -> str:
    if re.search(r'\bإشارة\b|\bسيجنال\b|\bSIGNAL\b|\bدخول\b|\bهدف\b', text, re.IGNORECASE):
        return "SIGNAL"
    if re.search(r'\bأعلنت\b|\bأرباح\b|\bتوزيع\b|\bعقد\b|\bearnings\b|\bdividend\b', text, re.IGNORECASE):
        return "NEWS"
    return "COMMENTARY"

def _parse_price(text: str, keyword: str) -> Optional[float]:
    pattern = rf'{keyword}[\s:]*(\d+(?:\.\d+)?)'
    m = re.search(pattern, text, re.IGNORECASE)
    return float(m.group(1)) if m else None

# ── DB helpers ───────────────────────────────────────────────────────────────
def _ensure_ksa_news_columns(conn):
    """Add KSA-specific columns to news table if missing."""
    cols = [
        ("ticker_mentions",  "TEXT"),
        ("direction",        "TEXT"),
        ("post_type",        "TEXT"),
        ("entry_price",      "NUMERIC(12,4)"),
        ("target_price",     "NUMERIC(12,4)"),
        ("stop_price",       "NUMERIC(12,4)"),
        ("views",            "INTEGER"),
        ("forwards",         "INTEGER"),
        ("has_media",        "BOOLEAN"),
        ("market_id",        "VARCHAR(10) DEFAULT 'KSA'"),
        ("channel_weight",   "NUMERIC(4,2)"),
    ]
    cur = conn.cursor()
    for col, dtype in cols:
        try:
            cur.execute(f"ALTER TABLE news ADD COLUMN IF NOT EXISTS {col} {dtype}")
            conn.commit()
        except Exception:
            conn.rollback()
    cur.close()

def _load_session_ksa(conn) -> Optional[bytes]:
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM system_config WHERE key = 'telegram_session_ksa'")
        row = cur.fetchone()
        cur.close()
        if row:
            return base64.b64decode(row[0])
    except Exception:
        pass
    return None

def _save_session_ksa(conn, session_bytes: bytes):
    encoded = base64.b64encode(session_bytes).decode()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO system_config(key, value, updated_at)
            VALUES('telegram_session_ksa', %s, NOW())
            ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """, (encoded,))
        conn.commit()
        cur.close()
    except Exception as e:
        logger.warning(f"[KSA] Failed to save Telegram session: {e}")

# ── Main pipeline ─────────────────────────────────────────────────────────────
def run_telegram_pipeline_ksa(conn, hours_back: int = 25):
    """
    Pull posts from KSA Telegram channels and insert into news table.
    Non-fatal: any error is logged and swallowed.
    """
    try:
        asyncio.run(_async_telegram_ksa(conn, hours_back))
    except Exception as e:
        logger.warning(f"[KSA] Telegram pipeline error (non-fatal): {e}")

async def _async_telegram_ksa(conn, hours_back: int):
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        logger.warning("[KSA] telethon not installed — skipping Telegram ingestion")
        return

    api_id   = int(os.environ.get("TELEGRAM_API_ID", "0"))
    api_hash = os.environ.get("TELEGRAM_API_HASH", "")
    if not api_id or not api_hash:
        logger.warning("[KSA] TELEGRAM_API_ID / TELEGRAM_API_HASH not set")
        return

    session_bytes = _load_session_ksa(conn)
    session_str   = session_bytes.decode() if session_bytes else ""

    _ensure_ksa_news_columns(conn)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    inserted = 0

    async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
        # Persist updated session
        if client.session.save():
            _save_session_ksa(conn, client.session.save().encode())

        for channel_name in KSA_CHANNELS:
            try:
                channel = await client.get_entity(channel_name)
                weight  = KSA_CHANNEL_WEIGHTS.get(channel_name, 0.50)

                async for msg in client.iter_messages(channel, limit=200):
                    if not msg.date or msg.date < cutoff:
                        break
                    if not msg.text:
                        continue

                    text    = msg.text
                    tickers = _extract_ksa_tickers(text)
                    if not tickers:
                        continue

                    direction = _parse_direction(text)
                    post_type = _parse_post_type(text)
                    entry     = _parse_price(text, r'دخول|entry|سعر الدخول')
                    target    = _parse_price(text, r'هدف|target')
                    stop      = _parse_price(text, r'وقف|stop|وقف الخسارة')

                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            INSERT INTO news
                                (title, date, source, market_id,
                                 ticker_mentions, direction, post_type,
                                 entry_price, target_price, stop_price,
                                 views, forwards, has_media, channel_weight)
                            VALUES (%s, %s, %s, 'KSA', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (
                            text[:500], msg.date, f"telegram:{channel_name}",
                            json.dumps(tickers), direction, post_type,
                            entry, target, stop,
                            getattr(msg, 'views', None),
                            getattr(msg, 'forwards', None),
                            bool(msg.media),
                            weight,
                        ))
                        conn.commit()
                        inserted += 1
                    except Exception as e:
                        conn.rollback()
                        logger.debug(f"[KSA] Insert failed: {e}")
                    finally:
                        cur.close()

            except Exception as e:
                logger.warning(f"[KSA] Channel {channel_name} error: {e}")

    logger.info(f"[KSA] Telegram pipeline complete — {inserted} messages inserted")


# ── First-run interactive setup ───────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Interactive first-run auth")
    args = parser.parse_args()

    if args.setup:
        import psycopg2
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        asyncio.run(_async_telegram_ksa(conn, hours_back=1))
        conn.close()
