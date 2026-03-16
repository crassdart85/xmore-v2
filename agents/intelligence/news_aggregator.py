"""
News Aggregator — Dedup, score, and store all intelligence items to DB.
Writes to existing `news` table (symbol, date, headline, source, url, sentiment_score).
Adds new columns via safe ALTER TABLE on first run.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Sentiment keywords ──────────────────────────────────────────
POSITIVE_AR = ["ارتفاع","نمو","ربح","توزيع","اختراق","فرصة","مستهدف","زيادة","صفقة","عقد جديد","تحسن"]
NEGATIVE_AR = ["انخفاض","خسارة","تراجع","غرامة","مخاوف","ضغوط","تأجيل","إلغاء","عجز","مخالفة","توقف"]
POSITIVE_EN = ["profit","growth","dividend","contract","beat","upgrade","expansion","record","acquisition","win"]
NEGATIVE_EN = ["loss","decline","fine","delay","miss","downgrade","default","investigation","fraud","suspend"]

SOURCE_WEIGHTS = {
    "egx_official": 0.9,
    "marketaux":    0.7,
    "mubasher":     0.7,
    "argaam":       0.6,
}

_columns_ensured = False


def ensure_news_columns(conn):
    """Add new columns to existing news table (idempotent)."""
    global _columns_ensured
    if _columns_ensured:
        return
    from database import DATABASE_URL, _safe_add_column
    cursor = conn.cursor()
    cols = [
        ("content_hash",       "VARCHAR(32)"),
        ("ticker",             "VARCHAR(10)"),
        ("urgency_score",      "REAL"),
        ("announcement_type",  "VARCHAR(20)"),
        ("is_material",        "BOOLEAN DEFAULT FALSE"),
        ("company_en",         "TEXT"),
        ("company_ar",         "TEXT"),
        ("language",           "VARCHAR(5)"),
        ("raw_json",           "TEXT"),
    ]
    for col, col_type in cols:
        _safe_add_column(cursor, "news", col, col_type)

    # Unique index on content_hash (non-blocking — skip if exists)
    if DATABASE_URL:
        cursor.execute("SAVEPOINT idx_content_hash")
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_news_content_hash ON news(content_hash) WHERE content_hash IS NOT NULL")
            cursor.execute("RELEASE SAVEPOINT idx_content_hash")
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT idx_content_hash")
    _columns_ensured = True


def _compute_sentiment(item: dict) -> float:
    if item.get("sentiment_score") is not None:
        try:
            return max(-1.0, min(1.0, float(item["sentiment_score"])))
        except (TypeError, ValueError):
            pass
    text = (item.get("headline", "") + " " + item.get("snippet", "")).lower()
    score = 0.0
    for kw in POSITIVE_AR + POSITIVE_EN:
        if kw.lower() in text:
            score += 0.15
    for kw in NEGATIVE_AR + NEGATIVE_EN:
        if kw.lower() in text:
            score -= 0.15
    return max(-1.0, min(1.0, score))


def _compute_urgency(item: dict) -> float:
    score = SOURCE_WEIGHTS.get(item.get("source", ""), 0.4)
    if item.get("is_material"):
        score += 0.3
    try:
        import dateutil.parser
        pub = dateutil.parser.parse(item.get("published_at", ""))
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        if age_hours < 2:
            score += 0.2
        elif age_hours < 6:
            score += 0.1
    except Exception:
        pass
    return min(1.0, score)


def aggregate_and_store(conn, items: list) -> dict:
    from database import DATABASE_URL
    from agents.intelligence.egx_universe import TICKER_BY_CA

    ensure_news_columns(conn)
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"
    new = dups = material = 0
    material_tickers = []

    for item in items:
        ticker = item.get("ticker", "")
        ticker_info = TICKER_BY_CA.get(ticker)
        if ticker_info:
            item["company_en"] = ticker_info[3]
            item["company_ar"] = ticker_info[2]

        # Content hash for dedup (ticker + first 80 chars of headline)
        key = f"{ticker}{item.get('headline','')[:80]}"
        item["content_hash"] = hashlib.md5(key.encode("utf-8")).hexdigest()

        item["sentiment_score"] = _compute_sentiment(item)
        item["urgency_score"]   = _compute_urgency(item)

        # Material event tracking
        if item.get("is_material"):
            material += 1
            if ticker and ticker not in material_tickers:
                material_tickers.append(ticker)
                logger.warning(f"[INTEL] ⚡ MATERIAL EVENT: {ticker} — {item.get('headline','')[:80]}")

        # Extract date from published_at
        pub_date = None
        try:
            import dateutil.parser
            pub_dt = dateutil.parser.parse(item.get("published_at", ""))
            pub_date = pub_dt.date().isoformat()
        except Exception:
            pub_date = datetime.now().date().isoformat()

        headline = item.get("headline", "")[:500]

        sql = (
            f"INSERT INTO news "
            f"(symbol, date, headline, source, url, "
            f"content_hash, sentiment_score, urgency_score, "
            f"announcement_type, is_material, "
            f"company_en, company_ar, language, raw_json, ticker) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})"
            + (" ON CONFLICT (content_hash) DO NOTHING" if DATABASE_URL else
               " ON CONFLICT (symbol, headline, date) DO NOTHING")
        )
        params = (
            ticker or "",
            pub_date,
            headline,
            item.get("source", ""),
            item.get("url", ""),
            item["content_hash"],
            item["sentiment_score"],
            item["urgency_score"],
            item.get("announcement_type"),
            item.get("is_material", False),
            item.get("company_en"),
            item.get("company_ar"),
            item.get("language", "en"),
            json.dumps({k: v for k, v in item.items() if k not in ("company_ar", "company_en", "content_hash")}),
            ticker or "",
        )
        if DATABASE_URL:
            cursor.execute("SAVEPOINT intel_insert")
        try:
            cursor.execute(sql, params)
            if DATABASE_URL:
                cursor.execute("RELEASE SAVEPOINT intel_insert")
            new += 1
        except Exception as e:
            if DATABASE_URL:
                cursor.execute("ROLLBACK TO SAVEPOINT intel_insert")
            err_str = str(e)
            if "unique" in err_str.lower() or "duplicate" in err_str.lower():
                dups += 1
            else:
                logger.debug(f"[INTEL:AGGREGATOR] Insert error for {ticker}: {e}")
                dups += 1

    logger.info(f"[INTEL:AGGREGATOR] {len(items)} items → {new} new, {dups} duplicates")
    return {
        "new_inserted":       new,
        "duplicates_skipped": dups,
        "material_events":    material_tickers,
    }
