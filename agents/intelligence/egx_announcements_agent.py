"""
EGX Announcements Agent — Official EGX corporate disclosures.
Highest signal-quality: earnings, dividends, capital events, insider trades.
"""
import logging
import requests
from datetime import datetime, timedelta, timezone

try:
    from bs4 import BeautifulSoup
    import dateutil.parser
except ImportError:
    BeautifulSoup = None
    dateutil = None

logger = logging.getLogger(__name__)

_MATERIAL_TYPES = {"EARNINGS", "CAPITAL_INCREASE", "MAJOR_SHAREHOLDER", "DIVIDEND"}


def fetch_egx_announcements(hours_back: float = 25) -> list:
    if BeautifulSoup is None:
        logger.warning("[INTEL:EGX] beautifulsoup4 not installed — skipping")
        return []

    from agents.intelligence.egx_universe import CA_TICKERS, EGX_TOP50

    HEADERS = {"User-Agent": "Mozilla/5.0 (Xmore/1.0)"}
    BASE = "https://www.egx.com.eg"
    announcements = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    try:
        resp = requests.get(f"{BASE}/en/Announcement.aspx", headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"[INTEL:EGX] HTTP {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, "lxml")

        rows = (
            soup.select("table.grid tr") or
            soup.select("div.announcement-row") or
            soup.select("tr[class*='Row']") or
            soup.select("table tr")
        )

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            date_str = cells[0].get_text(strip=True)
            company  = cells[1].get_text(strip=True)
            subject  = cells[2].get_text(strip=True)
            link_el  = row.find("a")
            url = BASE + link_el["href"] if link_el and link_el.get("href") else ""

            ticker = _match_ticker_from_text(company + " " + subject)
            if not ticker:
                continue

            try:
                pub_dt = dateutil.parser.parse(date_str, dayfirst=True)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pub_dt = datetime.now(timezone.utc)

            ann_type    = _classify_announcement(subject)
            is_material = ann_type in _MATERIAL_TYPES

            announcements.append({
                "source":            "egx_official",
                "ticker":            ticker,
                "headline":          subject[:500],
                "url":               url,
                "published_at":      pub_dt.isoformat(),
                "language":          "en",
                "announcement_type": ann_type,
                "is_material":       is_material,
                "sentiment_score":   None,
            })

    except Exception as e:
        logger.error(f"[INTEL:EGX] Fetch failed: {e}")

    material_count = sum(1 for a in announcements if a["is_material"])
    logger.info(f"[INTEL:EGX] {len(announcements)} announcements, {material_count} material")
    return announcements


def _match_ticker_from_text(text: str) -> str:
    from agents.intelligence.egx_universe import CA_TICKERS, EGX_TOP50
    text_upper = text.upper()
    for ca in CA_TICKERS:
        if ca in text_upper:
            return ca
    for t in EGX_TOP50:
        if t[3].lower() in text.lower():
            return t[0]
    for t in EGX_TOP50:
        if t[2] and t[2] in text:
            return t[0]
    return None


def _classify_announcement(subject: str) -> str:
    s = subject.lower()
    if any(k in s for k in ["financial result", "net profit", "revenue", "earnings",
                              "نتائج مالية", "صافي الربح"]):
        return "EARNINGS"
    if any(k in s for k in ["dividend", "توزيع أرباح"]):
        return "DIVIDEND"
    if any(k in s for k in ["capital increase", "زيادة رأس المال"]):
        return "CAPITAL_INCREASE"
    if any(k in s for k in ["major shareholder", "substantial holding",
                              "ownership", "ملكية", "مساهم رئيسي"]):
        return "MAJOR_SHAREHOLDER"
    if any(k in s for k in ["board of directors", "مجلس الإدارة"]):
        return "BOARD_DECISION"
    if any(k in s for k in ["contract", "agreement", "عقد", "اتفاقية"]):
        return "CONTRACT"
    if any(k in s for k in ["ipo", "listing", "إدراج"]):
        return "IPO_LISTING"
    if any(k in s for k in ["fine", "violation", "غرامة", "مخالفة"]):
        return "REGULATORY_ACTION"
    return "GENERAL"
