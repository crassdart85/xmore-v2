"""
Mubasher Agent — Scrapes Arabic + English news from mubasher.info.
Highest-value Arabic source for EGX companies.
"""
import time
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


def fetch_mubasher_news(hours_back: int = 25) -> list:
    if BeautifulSoup is None:
        logger.warning("[INTEL:MUBASHER] beautifulsoup4 not installed — skipping")
        return []

    from agents.intelligence.egx_universe import EGX_TOP50

    HEADERS = {"User-Agent": "Mozilla/5.0 (Xmore/1.0 research bot)"}
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    # Circuit-breaker: if 3 consecutive timeouts, stop scraping for that lang
    _consecutive_timeouts = {"en": 0, "ar": 0}
    _TIMEOUT_LIMIT = 3

    for ca_ticker, yahoo_ticker, name_ar, name_en, sector, slug in EGX_TOP50:
        for lang, base_url in [
            ("en", f"https://english.mubasher.info/markets/EGX/stocks/{slug}/news"),
            ("ar", f"https://mubasher.info/markets/EGX/stocks/{slug}/news/ar"),
        ]:
            if _consecutive_timeouts[lang] >= _TIMEOUT_LIMIT:
                continue  # skip remaining tickers for this lang
            try:
                resp = requests.get(base_url, headers=HEADERS, timeout=5)
                _consecutive_timeouts[lang] = 0  # reset on success
                if resp.status_code != 200:
                    time.sleep(0.5)
                    continue
                soup = BeautifulSoup(resp.text, "lxml")

                items = (
                    soup.select("div.news-item") or
                    soup.select("li.news-entry") or
                    soup.select("div[class*='article']") or
                    soup.select("div[class*='news']")
                )

                for item in items[:5]:
                    title_el = (
                        item.select_one("a[class*='title']") or
                        item.select_one("h3 a") or
                        item.select_one("h2 a") or
                        item.select_one("a")
                    )
                    date_el = (
                        item.select_one("time") or
                        item.select_one("span[class*='date']") or
                        item.select_one("span[class*='time']")
                    )
                    if not title_el:
                        continue

                    headline = title_el.get_text(strip=True)
                    if not headline:
                        continue
                    href = title_el.get("href", "")
                    if href.startswith("/"):
                        base = "https://english.mubasher.info" if lang == "en" else "https://mubasher.info"
                        href = f"{base}{href}"

                    pub_str = ""
                    if date_el:
                        pub_str = date_el.get("datetime") or date_el.get_text(strip=True)

                    try:
                        pub_dt = dateutil.parser.parse(pub_str, dayfirst=True)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        if pub_dt < cutoff:
                            continue
                    except Exception:
                        pub_dt = datetime.now(timezone.utc)

                    articles.append({
                        "source":          "mubasher",
                        "ticker":          ca_ticker,
                        "headline":        headline,
                        "url":             href,
                        "published_at":    pub_dt.isoformat(),
                        "language":        lang,
                        "sentiment_score": None,
                    })

            except requests.exceptions.Timeout:
                _consecutive_timeouts[lang] += 1
                logger.warning(f"[INTEL:MUBASHER] {ca_ticker}/{lang}: timeout ({_consecutive_timeouts[lang]}/{_TIMEOUT_LIMIT})")
                if _consecutive_timeouts[lang] >= _TIMEOUT_LIMIT:
                    logger.warning(f"[INTEL:MUBASHER] circuit breaker tripped for lang={lang}, skipping remaining tickers")
            except Exception as e:
                logger.error(f"[INTEL:MUBASHER] {ca_ticker}/{lang}: {e}")

            time.sleep(0.5)

    logger.info(f"[INTEL:MUBASHER] {len(articles)} articles scraped")
    return articles
