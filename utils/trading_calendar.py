"""
Trading calendar for EGX and US markets.
"""
from datetime import date

# EGX holidays 2026 (approximate — update annually)
EGX_HOLIDAYS_2026 = {
    date(2026, 1, 7),    # Christmas (Coptic)
    date(2026, 1, 25),   # Revolution Day
    date(2026, 3, 20),   # Eid al-Fitr (approx)
    date(2026, 3, 21),
    date(2026, 3, 22),
    date(2026, 4, 13),   # Sham El Nessim (approx)
    date(2026, 4, 25),   # Sinai Liberation Day
    date(2026, 5, 1),    # Labour Day
    date(2026, 5, 27),   # Eid al-Adha (approx)
    date(2026, 5, 28),
    date(2026, 5, 29),
    date(2026, 6, 17),   # Islamic New Year (approx)
    date(2026, 6, 30),   # June 30 Revolution
    date(2026, 7, 23),   # Revolution Day
    date(2026, 8, 26),   # Prophet's Birthday (approx)
    date(2026, 10, 6),   # Armed Forces Day
}

# US holidays 2026
US_HOLIDAYS_2026 = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King, Jr. Day
    date(2026, 2, 16),   # Washington's Birthday (Presidents' Day)
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth National Independence Day
    date(2026, 7, 3),    # Independence Day (Observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving Day
    date(2026, 12, 25),  # Christmas Day
}

def is_egx_trading_day(d: date = None) -> bool:
    """Check if a date is an EGX trading day (Sun-Thu, not holiday)."""
    d = d or date.today()
    # EGX trades Sun (6) through Thu (3)
    if d.weekday() in (4, 5):  # Friday, Saturday
        return False
    if d in EGX_HOLIDAYS_2026:
        return False
    return True

def is_us_trading_day(d: date = None) -> bool:
    """Check if a date is a US trading day (Mon-Fri, not holiday)."""
    d = d or date.today()
    if d.weekday() in (5, 6):  # Saturday, Sunday
        return False
    if d in US_HOLIDAYS_2026:
        return False
    return True

def get_market_for_symbol(symbol: str) -> str:
    """Determine which market a symbol belongs to."""
    if symbol.endswith('.CA'):
        return 'EGX'
    return 'US'

def should_generate_recommendations(d: date = None) -> dict:
    """Check which markets should get recommendations today."""
    d = d or date.today()
    return {
        "egx": is_egx_trading_day(d),
        "us": is_us_trading_day(d)
    }
