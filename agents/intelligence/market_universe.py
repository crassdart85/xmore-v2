"""KSA-first market universe helpers for intelligence agents."""

from config.ksa_universe import KSA_TOP50


TICKER_ROWS = [
    (
        stock["symbol"],
        stock["symbol"],
        stock["name_ar"],
        stock["name_en"],
        stock["sector_en"],
        None,
    )
    for stock in KSA_TOP50
]

TICKER_BY_SYMBOL = {row[0].upper(): row for row in TICKER_ROWS}
TICKERS = [row[0].upper() for row in TICKER_ROWS]

NAME_TO_SYMBOL = {}
for symbol, _yahoo, name_ar, name_en, _sector, _slug in TICKER_ROWS:
    if name_en:
        NAME_TO_SYMBOL[name_en.lower()] = symbol
    if name_ar:
        NAME_TO_SYMBOL[name_ar.lower()] = symbol


def normalize_symbol(raw_symbol: str | None) -> str | None:
    value = str(raw_symbol or "").strip().upper()
    if not value:
        return None
    if value in TICKER_BY_SYMBOL:
        return value
    if value.isdigit() and len(value) == 4:
        candidate = f"{value}.SR"
        if candidate in TICKER_BY_SYMBOL:
            return candidate
    return None


def match_ticker_from_text(text: str) -> str | None:
    haystack = str(text or "")
    if not haystack:
        return None

    upper_text = haystack.upper()
    for symbol in TICKERS:
        bare_symbol = symbol.replace(".SR", "")
        if symbol in upper_text or bare_symbol in upper_text:
            return symbol

    lower_text = haystack.lower()
    for company_name, symbol in NAME_TO_SYMBOL.items():
        if company_name and company_name in lower_text:
            return symbol

    return None