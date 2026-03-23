"""
EGX Announcements Agent — Corporate disclosures for Egyptian Exchange stocks.

Primary source: Mubasher market-wide announcements
    https://www.mubasher.info/countries/eg/announcements
  Mubasher is proven reachable from Render (used by etf_egx_mubasher.py).
  One request fetches all recent EGX filings — no per-ticker loop needed.

Fallback: yfinance .news per-ticker (English headlines only).

egx.com.eg is excluded: it drops TCP connections from cloud IPs (WAF block).
"""
import logging
import time
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

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Referer": "https://www.mubasher.info/",
}


def fetch_egx_announcements(hours_back: float = 25) -> list:
    announcements = _fetch_mubasher_announcements(hours_back)

    if not announcements:
        logger.debug("[INTEL:EGX] Mubasher returned 0 — trying yfinance fallback")
        announcements = _fetch_yfinance_news(hours_back)

    material_count = sum(1 for a in announcements if a.get("is_material"))
    logger.info(f"[INTEL:EGX] {len(announcements)} announcements, {material_count} material")
    return announcements


# ── Primary: Mubasher market-wide feed ────────────────────────────────────────

def _fetch_mubasher_announcements(hours_back: float) -> list:
    """
    Per-ticker scrape of English Mubasher announcements pages.
    URL: https://english.mubasher.info/markets/EGX/stocks/{slug}/announcements
    Same slug list used by mubasher_agent.py for news.
    Circuit breaker: stop after 3 consecutive timeouts.
    """
    if BeautifulSoup is None:
        return []

    from agents.intelligence.egx_universe import EGX_TOP50

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    _parser = "lxml" if __import__("importlib").util.find_spec("lxml") else "html.parser"
    BASE    = "https://english.mubasher.info"
    results = []
    consecutive_timeouts = 0
    _TIMEOUT_LIMIT = 3

    for ca_ticker, _yahoo, _name_ar, name_en, _sector, slug in EGX_TOP50:
        if consecutive_timeouts >= _TIMEOUT_LIMIT:
            break
        if not slug:
            continue
        url = f"{BASE}/markets/EGX/stocks/{slug}/announcements"
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            consecutive_timeouts = 0
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, _parser)
            # Mubasher uses: <div class="mi-announcement md-whiteframe-z1">
            #   <span class="mi-announcement__date">17 March 10:41 AM</span>
            #   <a>Headline text</a>
            rows = soup.find_all("div", class_=lambda c: c and "mi-announcement" in c)

            for row in rows:
                date_el  = row.find("span", class_="mi-announcement__date")
                date_str = date_el.get_text(strip=True) if date_el else ""
                pub_dt   = _parse_date_mubasher(date_str)
                if pub_dt < cutoff:
                    continue

                link_el  = row.find("a")
                href     = link_el.get("href", "") if link_el else ""
                if href and not href.startswith("http"):
                    href = BASE + href
                headline    = (link_el.get_text(strip=True) if link_el else row.get_text(" ", strip=True))[:500]
                ann_type    = _classify_announcement(headline)
                is_material = ann_type in _MATERIAL_TYPES

                results.append({
                    "source":            "mubasher_egx",
                    "ticker":            ca_ticker,
                    "headline":          headline,
                    "url":               href,
                    "published_at":      pub_dt.isoformat(),
                    "language":          "en",
                    "announcement_type": ann_type,
                    "is_material":       is_material,
                    "sentiment_score":   None,
                })

            time.sleep(0.3)

        except requests.exceptions.Timeout:
            consecutive_timeouts += 1
            logger.debug(f"[INTEL:EGX] Mubasher timeout {ca_ticker} ({consecutive_timeouts}/{_TIMEOUT_LIMIT})")
        except Exception as e:
            logger.debug(f"[INTEL:EGX] Mubasher {ca_ticker}: {e}")

    return results


# ── Fallback: yfinance .news ──────────────────────────────────────────────────

def _fetch_yfinance_news(hours_back: float) -> list:
    try:
        import yfinance as yf
    except ImportError:
        return []

    from agents.intelligence.egx_universe import EGX_TOP50

    cutoff  = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    results = []

    for ca_ticker, yahoo_ticker, *_ in EGX_TOP50:
        try:
            news_items = yf.Ticker(yahoo_ticker).news or []
            for item in news_items:
                pub_ts = item.get("providerPublishTime") or 0
                pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                if pub_dt < cutoff:
                    continue
                headline    = item.get("title", "")[:500]
                ann_type    = _classify_announcement(headline)
                is_material = ann_type in _MATERIAL_TYPES
                results.append({
                    "source":            "yfinance_news",
                    "ticker":            ca_ticker,
                    "headline":          headline,
                    "url":               item.get("link", ""),
                    "published_at":      pub_dt.isoformat(),
                    "language":          "en",
                    "announcement_type": ann_type,
                    "is_material":       is_material,
                    "sentiment_score":   None,
                })
        except Exception:
            pass

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_date(date_str: str):
    if not date_str or dateutil is None:
        return None
    try:
        dt = dateutil.parser.parse(date_str, dayfirst=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _parse_date_mubasher(date_str: str) -> datetime:
    """
    Parse Mubasher date strings like '17 March 10:41 AM' (no year).
    Assumes current year; if the resulting date is in the future, uses previous year.
    Falls back to now() on any failure.
    """
    now = datetime.now(timezone.utc)
    if not date_str or dateutil is None:
        return now
    try:
        # Inject current year so dateutil can parse "17 March 10:41 AM"
        dt = dateutil.parser.parse(f"{date_str} {now.year}", dayfirst=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # If parsed date is in the future (e.g., "31 Dec" in January), roll back one year
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=dt.year - 1)
        return dt
    except Exception:
        return now


def _match_ticker_from_text(text: str):
    from agents.intelligence.egx_universe import CA_TICKERS, EGX_TOP50
    text_upper = text.upper()
    for ca in CA_TICKERS:
        if ca in text_upper:
            return ca
    lower = text.lower()
    for t in EGX_TOP50:
        if t[3] and t[3].lower() in lower:
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
