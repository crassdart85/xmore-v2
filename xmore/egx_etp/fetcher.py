"""
xmore.egx_etp.fetcher
~~~~~~~~~~~~~~~~~~~~~
HTTP fetcher with Playwright fallback, retry logic, and raw-page archiving.

Public API
----------
fetch_html(url)       -> tuple[str, str]   (html_text, method)
archive_raw(url, method, html) -> str      (file path written)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAW_DIR = Path(os.environ.get("RAW_DIR", "./raw_pages"))

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.egx.com.eg/en/homepage.aspx",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

_BLOCK_PHRASES = [
    "Request Rejected",
    "The requested URL was rejected",
    "Access Denied",
    "403 Forbidden",
    "429 Too Many",
]

_TIMEOUT_S = 30
_PLAYWRIGHT_WAIT_MS = 8_000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_blocked(html: str, status: int) -> bool:
    """Return True if the response looks like a bot-block."""
    if status in (403, 429):
        return True
    for phrase in _BLOCK_PHRASES:
        if phrase.lower() in html.lower():
            return True
    return False


def _short_html(html: str) -> bool:
    """Return True if the body is suspiciously short (JS-shell page)."""
    return len(html.strip()) < 2_000


# ---------------------------------------------------------------------------
# Playwright fallback
# ---------------------------------------------------------------------------

def _fetch_via_playwright(url: str) -> str:
    """Render the page with Playwright/Chromium and return the full HTML."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    logger.info("Playwright fallback: %s", url)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            locale="en-US",
            extra_http_headers={
                "Accept-Language": _HEADERS["Accept-Language"],
                "Referer": _HEADERS["Referer"],
            },
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60_000)
        # Extra wait for ASP.NET pages that fire __doPostBack on load
        try:
            page.wait_for_load_state("networkidle", timeout=_PLAYWRIGHT_WAIT_MS)
        except Exception:
            pass
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
def fetch_html(url: str) -> tuple[str, str]:
    """
    Fetch *url* and return ``(html_text, method)`` where method is
    ``"requests"`` or ``"playwright"``.

    Raises
    ------
    RuntimeError
        If all attempts fail after retries.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # --- Attempt 1: requests ---
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT_S)
        html = resp.text
        if not _is_blocked(html, resp.status_code) and not _short_html(html):
            logger.info("requests OK  [%d] %s  (%d bytes)", resp.status_code, url, len(html))
            return html, "requests"
        logger.warning(
            "requests returned blocked/short page [%d, %d bytes] for %s — trying Playwright",
            resp.status_code, len(html), url,
        )
    except requests.RequestException as exc:
        logger.warning("requests error for %s: %s — trying Playwright", url, exc)

    # --- Attempt 2: Playwright ---
    html = _fetch_via_playwright(url)
    if _short_html(html):
        logger.warning("Playwright also returned short page (%d bytes) for %s", len(html), url)
    else:
        logger.info("Playwright OK  %s  (%d bytes)", url, len(html))
    return html, "playwright"


def archive_raw(url: str, method: str, html: str) -> str:
    """
    Save *html* to ``RAW_DIR`` and return the absolute file path written.

    Filename pattern: ``<sha8>_<timestamp_utc>.html``
    A companion ``.meta.json`` is written alongside with url/method/timestamp.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = hashlib.sha1(url.encode()).hexdigest()[:8]
    stem = f"{sha}_{ts}"

    html_path = RAW_DIR / f"{stem}.html"
    meta_path = RAW_DIR / f"{stem}.meta.json"

    html_path.write_text(html, encoding="utf-8")
    meta_path.write_text(
        json.dumps({"url": url, "method": method, "fetched_at": ts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug("Archived %s → %s", url, html_path)
    return str(html_path.resolve())
