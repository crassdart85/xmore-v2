"""
KSA (Saudi Arabia) Market Calendar
===================================
Shared holiday calendar and trading-day helpers for the Tadawul (Saudi Exchange).

Tadawul trading week: Sunday–Thursday (Fri/Sat = weekend).
Trading hours: 10:00–15:00 AST (07:00–12:00 UTC), no DST.

Usage:
    from config.ksa_holidays import is_saudi_holiday, is_trading_day, SAUDI_HOLIDAYS

These holidays are Gregorian estimates for Islamic dates; update yearly.
"""

import datetime

# --------------------------------------------------------------------------
# Saudi national holidays 2025-2026 (Gregorian calendar equivalents).
# Sources: Saudi official calendar — Founding Day, Eid al-Fitr, Eid al-Adha,
# National Day, Islamic New Year, Prophet's Birthday.
# --------------------------------------------------------------------------

SAUDI_HOLIDAYS_2025 = frozenset([
    datetime.date(2025, 2, 22),   # Founding Day
    # Eid al-Fitr (estimated)
    datetime.date(2025, 3, 30),
    datetime.date(2025, 3, 31),
    datetime.date(2025, 4, 1),
    datetime.date(2025, 4, 2),
    datetime.date(2025, 4, 3),
    # Eid al-Adha (estimated)
    datetime.date(2025, 6, 6),
    datetime.date(2025, 6, 7),
    datetime.date(2025, 6, 8),
    datetime.date(2025, 6, 9),
    datetime.date(2025, 6, 10),
    datetime.date(2025, 9, 23),   # National Day
])

SAUDI_HOLIDAYS_2026 = frozenset([
    datetime.date(2026, 2, 22),   # Founding Day
    # Eid al-Fitr (estimated)
    datetime.date(2026, 3, 20),
    datetime.date(2026, 3, 21),
    datetime.date(2026, 3, 22),
    # Eid al-Adha (estimated)
    datetime.date(2026, 5, 27),
    datetime.date(2026, 5, 28),
    datetime.date(2026, 5, 29),
    datetime.date(2026, 5, 30),
    # Islamic New Year (estimated)
    datetime.date(2026, 6, 17),
    # Prophet's Birthday (estimated)
    datetime.date(2026, 8, 25),
    datetime.date(2026, 9, 23),   # National Day
])

# Combined set for quick membership checks
SAUDI_HOLIDAYS = SAUDI_HOLIDAYS_2025 | SAUDI_HOLIDAYS_2026

# Tadawul trading week: Sunday=6, Monday=0, Tuesday=1, Wednesday=2, Thursday=3
_TADAWUL_TRADING_WEEKDAYS = {6, 0, 1, 2, 3}


def is_saudi_holiday(check_date: datetime.date = None) -> bool:
    """Return True if check_date (default today) is a Saudi public holiday."""
    if check_date is None:
        check_date = datetime.date.today()
    return check_date in SAUDI_HOLIDAYS


def is_tadawul_weekend(check_date: datetime.date = None) -> bool:
    """Return True if check_date falls on Fri or Sat (Tadawul weekend)."""
    if check_date is None:
        check_date = datetime.date.today()
    return check_date.weekday() in (4, 5)  # Friday=4, Saturday=5


def is_trading_day(check_date: datetime.date = None) -> bool:
    """Return True if check_date is a normal Tadawul trading day (not weekend, not holiday)."""
    if check_date is None:
        check_date = datetime.date.today()
    if check_date.weekday() not in _TADAWUL_TRADING_WEEKDAYS:
        return False
    if check_date in SAUDI_HOLIDAYS:
        return False
    return True
