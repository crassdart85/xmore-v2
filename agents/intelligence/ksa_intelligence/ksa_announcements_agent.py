"""
KSA Announcements Agent — scrapes official Saudi Exchange issuer announcements.
Primary URL: Saudi Exchange portal issuer-announcements page.
"""
import logging
import time
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

ANNOUNCEMENT_URL = (
    "https://www.saudiexchange.sa/wps/portal/saudiexchange/"
    "newsandreports/issuer-news/issuer-announcements"
)
SOURCE_WEIGHT = 0.90
MARKET_ID     = "KSA"

EVENT_TYPES = {
    "EARNINGS":          ["أرباح", "earnings", "net income", "صافي الربح", "نتائج"],
    "DIVIDEND":          ["توزيع", "dividend", "أرباح موزعة", "distribution"],
    "CAPITAL_INCREASE":  ["زيادة رأس المال", "capital increase", "rights issue"],
    "BOARD_DECISION":    ["قرار مجلس", "board", "اجتماع مجلس الإدارة"],
    "CONTRACT":          ["عقد", "contract", "اتفاقية", "agreement", "مناقصة"],
    "REGULATORY_ACTION": ["هيئة السوق المالية", "CMA", "غرامة", "fine", "تحقيق"],
}
MATERIAL_TYPES = {"EARNINGS", "DIVIDEND", "CAPITAL_INCREASE"}


def _classify_event(text: str) -> tuple:
    """Returns (event_type, is_material)."""
    text_lower = text.lower()
    for etype, keywords in EVENT_TYPES.items():
        if any(k.lower() in text_lower for k in keywords):
            return etype, etype in MATERIAL_TYPES
    return "GENERAL", False


def _extract_ticker_from_text(text: str) -> Optional[str]:
    """Try to extract a 4-digit code from announcement text."""
    from config.ksa_universe import KSA_TICKER_CODES
    m = re.search(r'\b(\d{4})\b', text)
    if m and m.group(1) in KSA_TICKER_CODES:
        return f"{m.group(1)}.SR"
    return None


def fetch_ksa_announcements(conn, hours_back: int = 25) -> list:
    """
    Scrape Saudi Exchange announcements and insert into ksa_material_events.
    Returns list of material ticker symbols.
    Non-fatal — errors are logged and swallowed.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("[KSA] requests/beautifulsoup4 not installed — skipping announcements")
        return []

    material_tickers = []
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    try:
        r = requests.get(ANNOUNCEMENT_URL, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # Find announcement rows — adapt selector to actual page structure
        rows = soup.find_all(["tr", "li"], class_=re.compile(r"announc|news|row", re.I))
        if not rows:
            rows = soup.find_all("a", href=re.compile(r"announcement|issuer", re.I))

        for row in rows[:50]:
            text = row.get_text(" ", strip=True)
            if not text:
                continue

            ticker    = _extract_ticker_from_text(text)
            etype, is_material = _classify_event(text)
            urgency   = 0.9 if is_material else 0.5

            _insert_event(conn, ticker, etype, text[:500], is_material, urgency)

            if is_material and ticker:
                material_tickers.append(ticker)

            time.sleep(0.5)

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            logger.info("[KSA] Announcements: saudiexchange.sa blocked (403) — skipping")
        else:
            logger.warning(f"[KSA] Announcements scrape error (non-fatal): {e}")
    except Exception as e:
        logger.warning(f"[KSA] Announcements scrape error (non-fatal): {e}")

    logger.info(f"[KSA] Announcements: {len(material_tickers)} material events")
    return list(set(material_tickers))


def _insert_event(conn, ticker, event_type, headline, is_material, urgency):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ksa_material_events
                (ticker, market_id, event_type, headline, source, is_material,
                 urgency_score, published_at)
            VALUES (%s, 'KSA', %s, %s, 'saudi_exchange', %s, %s, NOW())
        """, (ticker, event_type, headline, is_material, urgency))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.debug(f"[KSA] Event insert error: {e}")
    finally:
        cur.close()
