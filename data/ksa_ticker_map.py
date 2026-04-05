"""
KSA Unified Ticker Map — Xmore Saudi Intelligence Layer.

Normalizes identifiers across all data sources:
  - Yahoo Finance / yfinance  →  "2010.SR"
  - Argaam                    →  "sabic" (URL slug)
  - EODHD                     →  "2010.SR" (same as Yahoo)
  - Display short code        →  "2010"
  - English name              →  "SABIC"
  - Arabic name               →  "سابك"

Usage:
    from data.ksa_ticker_map import KSA_TICKER_MAP, symbol_to_name, name_to_symbol

All lookups are O(1) dict access. Build once at import time from ksa_universe.
"""

from config.ksa_universe import KSA_TOP50

# ---------------------------------------------------------------------------
# Primary map: symbol → metadata dict
# ---------------------------------------------------------------------------
KSA_TICKER_MAP: dict[str, dict] = {
    s["symbol"]: {
        "symbol":       s["symbol"],            # "2010.SR"
        "short_code":   s["symbol"].split(".")[0],  # "2010"
        "name_en":      s["name_en"],           # "SABIC"
        "name_ar":      s["name_ar"],           # "سابك"
        "sector_en":    s["sector_en"],
        "sector_ar":    s["sector_ar"],
        "argaam_slug":  _make_argaam_slug(s["name_en"]),
        "eodhd_ticker": s["symbol"],            # same format as yfinance
    }
    for s in KSA_TOP50
}

# Build reverse-lookup tables at import time
_short_to_symbol: dict[str, str] = {
    v["short_code"]: k for k, v in KSA_TICKER_MAP.items()
}
_name_en_to_symbol: dict[str, str] = {
    v["name_en"].upper(): k for k, v in KSA_TICKER_MAP.items()
}


def _make_argaam_slug(name_en: str) -> str:
    """
    Generate an Argaam URL slug from an English company name.
    e.g. "Saudi Aramco" → "saudi-aramco"
         "SABIC"        → "sabic"
    """
    import re
    slug = name_en.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def symbol_to_name(symbol: str, lang: str = "en") -> str:
    """
    "2010.SR" → "SABIC"  (lang="en")
    "2010.SR" → "سابك"   (lang="ar")
    Returns symbol unchanged if not found.
    """
    meta = KSA_TICKER_MAP.get(symbol.upper())
    if not meta:
        return symbol
    return meta["name_ar"] if lang == "ar" else meta["name_en"]


def symbol_to_short(symbol: str) -> str:
    """"2010.SR" → "2010" """
    return symbol.split(".")[0] if "." in symbol else symbol


def short_to_symbol(code: str) -> str:
    """"2010" → "2010.SR". Returns "CODE.SR" fallback if not in universe."""
    return _short_to_symbol.get(code, f"{code}.SR")


def name_to_symbol(name: str) -> str | None:
    """
    "SABIC" → "2010.SR"  (case-insensitive English match).
    Returns None if not found.
    """
    return _name_en_to_symbol.get(name.upper())


def symbol_to_sector(symbol: str, lang: str = "en") -> str:
    """"2010.SR" → "Petrochemicals" """
    meta = KSA_TICKER_MAP.get(symbol.upper())
    if not meta:
        return "Unknown"
    return meta["sector_ar"] if lang == "ar" else meta["sector_en"]


def symbol_to_argaam_slug(symbol: str) -> str:
    """"2010.SR" → "sabic" (for constructing Argaam URLs)"""
    meta = KSA_TICKER_MAP.get(symbol.upper())
    return meta["argaam_slug"] if meta else symbol_to_short(symbol).lower()


def normalize_ticker(raw: str) -> str:
    """
    Accept any of: "2010", "2010.SR", "SABIC", "sabic"
    and return the canonical ".SR" symbol.

    Returns raw input (uppercased) if unresolvable.
    """
    raw = raw.strip().upper()

    # Already a full symbol
    if raw in KSA_TICKER_MAP:
        return raw

    # Bare 4-digit code
    candidate = _short_to_symbol.get(raw)
    if candidate:
        return candidate

    # English name
    candidate = _name_en_to_symbol.get(raw)
    if candidate:
        return candidate

    # Try adding .SR suffix
    with_sr = f"{raw}.SR"
    if with_sr in KSA_TICKER_MAP:
        return with_sr

    return raw


def all_symbols() -> list[str]:
    """Return all .SR symbols in the KSA universe."""
    return list(KSA_TICKER_MAP.keys())


def all_sectors() -> list[str]:
    """Return unique sector names (English)."""
    return list({v["sector_en"] for v in KSA_TICKER_MAP.values()})
