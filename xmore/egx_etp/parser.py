"""
xmore.egx_etp.parser
~~~~~~~~~~~~~~~~~~~~
HTML parsers for every EGX ETP page.

Public API
----------
parse_trading_page(html, url)   -> List[ProductCard]
parse_holdings_page(html)       -> List[HoldingRow]
parse_nav_page(html)            -> List[NavRecord]
parse_fund_volume_page(html)    -> List[VolumeRecord]
parse_structured_products(html) -> List[dict]
parse_num(value)                -> Optional[float]
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from xmore.egx_etp.models import HoldingRow, NavRecord, ProductCard, VolumeRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# EGX instrument codes are 2–8 uppercase-ish alphanumeric characters
_CODE_RE = re.compile(r"^[A-Za-z0-9]{2,8}$")

# Date pattern: DD/MM/YYYY or YYYY-MM-DD
_DATE_RE = re.compile(r"\d{1,4}[/\-]\d{1,2}[/\-]\d{2,4}")


def parse_num(value: str) -> Optional[float]:
    """
    Convert a display string like ``"1,234.56"``, ``"-"`` or ``"3.2%"`` to float.
    Returns ``None`` for empty / dash / non-numeric values.
    """
    if not value:
        return None
    cleaned = value.strip().replace(",", "").replace("%", "").replace("\u202f", "")
    if cleaned in ("-", "--", "N/A", "n/a", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _text(tag: Optional[Tag]) -> str:
    if tag is None:
        return ""
    return tag.get_text(separator=" ", strip=True)


def _cells(row: Tag) -> List[str]:
    return [_text(td) for td in row.find_all(["td", "th"])]


def _find_header_map(header_row: Tag, *candidates: str) -> Dict[str, int]:
    """
    Return a dict mapping lowercased column name → column index for the
    first row whose headers match any of the *candidates* lists.
    """
    texts = [_text(th).lower() for th in header_row.find_all(["th", "td"])]
    return {t: i for i, t in enumerate(texts)}


def _is_code(s: str) -> bool:
    return bool(_CODE_RE.match(s.strip()))


def _today_str() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Trading page parser
# ---------------------------------------------------------------------------

def _parse_trading_cards(soup: BeautifulSoup, url: str) -> List[ProductCard]:
    """Try card-style layout first."""
    cards: List[ProductCard] = []
    # EGX sometimes wraps each ETP in a <div class="...fund..."> or <div class="...etf...">
    containers = (
        soup.find_all("div", class_=re.compile(r"(fund|etf|etp|product)", re.I))
        or soup.find_all("div", class_=re.compile(r"item", re.I))
    )
    for div in containers:
        raw = _text(div)
        # must contain something that looks like a code
        tokens = raw.split()
        code_candidates = [t for t in tokens if _is_code(t) and t.upper() == t]
        if not code_candidates:
            continue
        code = code_candidates[0]
        nums = [parse_num(t) for t in tokens if parse_num(t) is not None]
        cards.append(
            ProductCard(
                code=code,
                arabic_name=None,
                english_name=None,
                close_price=nums[0] if len(nums) > 0 else None,
                change_pct=nums[1] if len(nums) > 1 else None,
                nav_value=nums[2] if len(nums) > 2 else None,
                prem_disc=nums[3] if len(nums) > 3 else None,
                source_url=url,
                raw_text=raw[:500],
            )
        )
    return cards


def _parse_trading_table(soup: BeautifulSoup, url: str) -> List[ProductCard]:
    """Fall back to parsing <table> rows."""
    cards: List[ProductCard] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        hmap = _find_header_map(rows[0])

        # Identify likely column indices by common header keywords
        def col(*keywords: str) -> Optional[int]:
            for kw in keywords:
                for h, i in hmap.items():
                    if kw in h:
                        return i
            return None

        code_col = col("code", "symbol", "ticker")
        ar_col = col("arabic", "عربي", "name")
        en_col = col("english", "fund name", "name")
        price_col = col("close", "price", "last")
        chg_col = col("change", "chg", "%")
        nav_col = col("nav")
        pd_col = col("prem", "disc", "premium")

        if code_col is None and ar_col is None and en_col is None:
            # No recognisable headers — try positional heuristics
            code_col = 0

        seen: set[str] = set()
        for row in rows[1:]:
            cells = _cells(row)
            if not cells:
                continue

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            raw_code = get(code_col).strip().upper()
            if not raw_code or raw_code in seen:
                continue
            if not _is_code(raw_code):
                # Maybe code is embedded in another column
                for c in cells[:4]:
                    if _is_code(c.strip()):
                        raw_code = c.strip().upper()
                        break
                else:
                    continue
            seen.add(raw_code)

            raw_text = " | ".join(cells)
            cards.append(
                ProductCard(
                    code=raw_code,
                    arabic_name=get(ar_col) or None,
                    english_name=get(en_col) or None,
                    close_price=parse_num(get(price_col)),
                    change_pct=parse_num(get(chg_col)),
                    nav_value=parse_num(get(nav_col)),
                    prem_disc=parse_num(get(pd_col)),
                    source_url=url,
                    raw_text=raw_text[:500],
                )
            )
    return cards


def _deduplicate(cards: List[ProductCard]) -> List[ProductCard]:
    seen: set[str] = set()
    out: List[ProductCard] = []
    for c in cards:
        if c.code not in seen:
            seen.add(c.code)
            out.append(c)
    return out


def parse_trading_page(html: str, url: str) -> List[ProductCard]:
    """
    Parse the EGX ETF/ETP trading data page.

    Tries card-style layout first; falls back to table rows.
    Returns a deduplicated list of :class:`ProductCard`.
    """
    soup = BeautifulSoup(html, "lxml")
    cards = _parse_trading_cards(soup, url)
    if not cards:
        logger.debug("No card containers found — trying table parser")
        cards = _parse_trading_table(soup, url)

    if not cards:
        logger.warning("parse_trading_page: no products extracted from %s", url)
    else:
        logger.info("parse_trading_page: %d products before dedup", len(cards))

    cards = _deduplicate(cards)
    logger.info("parse_trading_page: %d unique products", len(cards))
    return cards


# ---------------------------------------------------------------------------
# Holdings page parser
# ---------------------------------------------------------------------------

def parse_holdings_page(html: str) -> List[HoldingRow]:
    """
    Parse the EGX Fund Constituents page.

    Looks for tables that contain columns for fund code, symbol/name, and weight.
    """
    soup = BeautifulSoup(html, "lxml")
    rows: List[HoldingRow] = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        if len(table_rows) < 2:
            continue
        hmap = _find_header_map(table_rows[0])

        def col(*keywords: str) -> Optional[int]:
            for kw in keywords:
                for h, i in hmap.items():
                    if kw in h:
                        return i
            return None

        fund_col = col("fund", "code", "ticker", "etf")
        sym_col = col("symbol", "stock", "constituent")
        name_col = col("name", "company", "security")
        wt_col = col("weight", "wt", "%", "share")
        date_col = col("date", "update")

        if fund_col is None:
            # Try to find via content heuristics — first column with short codes
            fund_col = 0

        for row in table_rows[1:]:
            cells = _cells(row)
            if not cells:
                continue

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            fund_code = get(fund_col).strip().upper()
            if not fund_code or not _is_code(fund_code):
                continue

            rows.append(
                HoldingRow(
                    fund_code=fund_code,
                    holding_symbol=get(sym_col).strip().upper() or None,
                    holding_name=get(name_col) or None,
                    weight_pct=parse_num(get(wt_col)),
                    last_update_date=get(date_col) or None,
                )
            )

    logger.info("parse_holdings_page: %d holding rows", len(rows))
    return rows


# ---------------------------------------------------------------------------
# NAV page parser
# ---------------------------------------------------------------------------

def parse_nav_page(html: str) -> List[NavRecord]:
    """
    Parse the EGX NAV Unit page.

    Looks for tables with fund code + NAV + date columns.
    """
    soup = BeautifulSoup(html, "lxml")
    records: List[NavRecord] = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        if len(table_rows) < 2:
            continue
        hmap = _find_header_map(table_rows[0])

        def col(*keywords: str) -> Optional[int]:
            for kw in keywords:
                for h, i in hmap.items():
                    if kw in h:
                        return i
            return None

        fund_col = col("code", "fund", "ticker", "symbol")
        nav_col = col("nav", "unit", "value")
        date_col = col("date", "update", "as of")

        if fund_col is None:
            fund_col = 0

        for row in table_rows[1:]:
            cells = _cells(row)
            if not cells:
                continue

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            fund_code = get(fund_col).strip().upper()
            if not fund_code or not _is_code(fund_code):
                continue

            nav_raw = get(nav_col) if nav_col is not None else ""
            date_raw = get(date_col) if date_col is not None else ""
            # If no date column, look for a date-shaped string anywhere in the row
            if not date_raw:
                for c in cells:
                    if _DATE_RE.search(c):
                        date_raw = c
                        break

            records.append(
                NavRecord(
                    fund_code=fund_code,
                    nav_value=parse_num(nav_raw),
                    nav_date=date_raw.strip() or _today_str(),
                )
            )

    logger.info("parse_nav_page: %d NAV records", len(records))
    return records


# ---------------------------------------------------------------------------
# Fund volume page parser
# ---------------------------------------------------------------------------

def parse_fund_volume_page(html: str) -> List[VolumeRecord]:
    """
    Parse the EGX ETF Fund Volume page.

    Expects columns: fund code, volume (shares), value (EGP), date.
    """
    soup = BeautifulSoup(html, "lxml")
    records: List[VolumeRecord] = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        if len(table_rows) < 2:
            continue
        hmap = _find_header_map(table_rows[0])

        def col(*keywords: str) -> Optional[int]:
            for kw in keywords:
                for h, i in hmap.items():
                    if kw in h:
                        return i
            return None

        fund_col = col("code", "fund", "ticker", "symbol")
        vol_col = col("volume", "vol", "quantity", "shares")
        val_col = col("value", "amount", "turnover")
        date_col = col("date", "session", "as of")

        if fund_col is None:
            fund_col = 0

        for row in table_rows[1:]:
            cells = _cells(row)
            if not cells:
                continue

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            fund_code = get(fund_col).strip().upper()
            if not fund_code or not _is_code(fund_code):
                continue

            vol_raw = get(vol_col) if vol_col is not None else ""
            val_raw = get(val_col) if val_col is not None else ""
            date_raw = get(date_col) if date_col is not None else _today_str()

            vol_f = parse_num(vol_raw)
            vol_i = int(vol_f) if vol_f is not None else None

            records.append(
                VolumeRecord(
                    fund_code=fund_code,
                    volume=vol_i,
                    value=parse_num(val_raw),
                    date=date_raw.strip() or _today_str(),
                )
            )

    logger.info("parse_fund_volume_page: %d volume records", len(records))
    return records


# ---------------------------------------------------------------------------
# Structured products page parser
# ---------------------------------------------------------------------------

def parse_structured_products(html: str) -> List[dict]:
    """
    Parse the EGX Structured Products page for taxonomy reference.

    Returns a list of dicts with keys: code, name, issuer, type.
    Used to enrich the classifier (codes known to be structured notes/ETNs).
    """
    soup = BeautifulSoup(html, "lxml")
    products: List[dict] = []

    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        if len(table_rows) < 2:
            continue
        hmap = _find_header_map(table_rows[0])

        def col(*keywords: str) -> Optional[int]:
            for kw in keywords:
                for h, i in hmap.items():
                    if kw in h:
                        return i
            return None

        code_col = col("code", "symbol", "ticker")
        name_col = col("name", "product", "description")
        issuer_col = col("issuer", "bank", "institution")
        type_col = col("type", "class", "category")

        if code_col is None:
            code_col = 0

        for row in table_rows[1:]:
            cells = _cells(row)
            if not cells:
                continue

            def get(idx: Optional[int]) -> str:
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx]

            code = get(code_col).strip().upper()
            if not code:
                continue

            products.append(
                {
                    "code": code,
                    "name": get(name_col) or None,
                    "issuer": get(issuer_col) or None,
                    "type": get(type_col) or None,
                }
            )

    logger.info("parse_structured_products: %d structured product records", len(products))
    return products
