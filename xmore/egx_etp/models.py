"""
xmore.egx_etp.models
~~~~~~~~~~~~~~~~~~~~
Dataclasses for all EGX ETP domain objects produced by the scraping pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProductCard:
    """One ETP instrument as seen on the EGX trading page."""

    code: str
    arabic_name: Optional[str]
    english_name: Optional[str]
    close_price: Optional[float]
    change_pct: Optional[float]
    nav_value: Optional[float]
    prem_disc: Optional[float]
    source_url: str
    raw_text: str


@dataclass
class HoldingRow:
    """One constituent line from the fund constituents page."""

    fund_code: str
    holding_symbol: Optional[str]
    holding_name: Optional[str]
    weight_pct: Optional[float]
    last_update_date: Optional[str]


@dataclass
class NavRecord:
    """NAV unit record for one fund on one date."""

    fund_code: str
    nav_value: Optional[float]
    nav_date: Optional[str]


@dataclass
class VolumeRecord:
    """Fund volume / value record."""

    fund_code: str
    volume: Optional[int]
    value: Optional[float]
    date: Optional[str]


@dataclass
class ClassificationResult:
    """Output of the instrument classifier."""

    instrument_type: str          # one of INSTRUMENT_TYPES
    confidence: float             # 0.0 – 1.0
    reason: str                   # human-readable explanation
    underlying_exposure: Optional[str]
    issuer: Optional[str]
