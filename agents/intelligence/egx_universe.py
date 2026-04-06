"""
KSA Top-50 Universe — canonical ticker/name/sector lookup for the intelligence system.
Each tuple: (short_ticker, yahoo_ticker, name_ar, name_en, sector, slug)

Legacy variable names (EGX_TOP50, CA_TICKERS, etc.) are retained for backward
compatibility with existing consumers.
"""

from config.ksa_universe import KSA_TOP50 as _KSA_TOP50

# Build the same tuple format expected by consumers:
# (short_ticker, yahoo_ticker, name_ar, name_en, sector, slug)
EGX_TOP50 = [
    (
        entry["symbol"].replace(".SR", ""),  # short ticker (e.g. "2222")
        entry["symbol"],                     # yahoo ticker (e.g. "2222.SR")
        entry["name_ar"],
        entry["name_en"],
        entry["sector_en"],
        entry["symbol"].replace(".SR", "").lower(),  # slug
    )
    for entry in _KSA_TOP50
]

# Lookup: short ticker → full tuple
TICKER_BY_CA: dict = {row[0]: row for row in EGX_TOP50}

# Lookup: English name (lower) → short ticker
TICKER_BY_NAME: dict = {row[3].lower(): row[0] for row in EGX_TOP50}

# All short tickers as a list
CA_TICKERS: list = [row[0] for row in EGX_TOP50]

# All Yahoo tickers (with .SR suffix)
YAHOO_TICKERS: list = [row[1] for row in EGX_TOP50]
