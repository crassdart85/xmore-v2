"""
xmore.egx_etp.classifier
~~~~~~~~~~~~~~~~~~~~~~~~~
Conservative instrument-type classifier for EGX ETPs.

Rules
-----
- ETF              : has fund constituents (holdings_available) AND/OR NAV unit
- GOLD_ETP         : name mentions gold / ذهب / دهب
- INDEX_TRACKER    : name references EGX30 / EGX70 / EGX100 / index but no holdings
- STRUCTURED_NOTE  : bank/issuer naming pattern (بنك/bank/certificate/note) + no holdings
- ETN              : code found in structured_products_codes or synthetic exposure without basket
- UNKNOWN_ETP      : insufficient evidence for any of the above

Classification is additive: the first matching rule that clears the
confidence threshold (>=0.5) wins.  All matches are attempted in order of
confidence so that the highest-confidence label is returned.

Conservative principle
----------------------
Never invent issuer or exposure — only populate them when the evidence is
explicit.  Mark unknowns as None.
"""

from __future__ import annotations

import re
from typing import Optional

from xmore.egx_etp.models import ClassificationResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTRUMENT_TYPES = [
    "ETF",
    "GOLD_ETP",
    "INDEX_TRACKER",
    "STRUCTURED_NOTE",
    "ETN",
    "UNKNOWN_ETP",
]

# Issuer name patterns (substring match, case-insensitive)
ISSUER_MAP: dict[str, str] = {
    "arab african": "Arab African International Bank",
    "العربي الأفريقي": "Arab African International Bank",
    "aaib": "Arab African International Bank",
    "pioneers": "Pioneers Holding",
    "بايونيرز": "Pioneers Holding",
    "beltone": "Beltone Financial",
    "بلتون": "Beltone Financial",
    "ci capital": "CI Capital",
    "سي آي": "CI Capital",
    "efg": "EFG Hermes",
    "هيرمس": "EFG Hermes",
    "mubasher": "Mubasher Financial",
    "مباشر": "Mubasher Financial",
    "nbe": "National Bank of Egypt",
    "البنك الأهلي": "National Bank of Egypt",
    "cib": "Commercial International Bank",
    "التجاري الدولي": "Commercial International Bank",
}

# Gold keywords (Arabic variants included)
_GOLD_KW = re.compile(r"gold|ذهب|دهب|golden", re.IGNORECASE)

# Index-tracking keywords
_INDEX_KW = re.compile(r"EGX\s*30|EGX\s*70|EGX\s*100|index\s*track|tracker|مؤشر", re.IGNORECASE)

# Structured note / issuer-type keywords
_STRUCT_KW = re.compile(
    r"bank|بنك|certificate|note|شهادة|وثيقة|سند|warrant|covered\s*warrant|certificate\s*of\s*deposit",
    re.IGNORECASE,
)

# ETF keywords — when name explicitly says ETF / صندوق
_ETF_KW = re.compile(r"\betf\b|exchange.traded|صندوق", re.IGNORECASE)

# Gold exposure patterns for underlying_exposure
_GOLD_EXPOSURE = "gold"

# Confidence thresholds
_HIGH = 0.85
_MED = 0.65
_LOW = 0.45


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _combined_name(arabic: Optional[str], english: Optional[str]) -> str:
    parts = []
    if arabic:
        parts.append(arabic)
    if english:
        parts.append(english)
    return " ".join(parts)


def _infer_issuer(combined: str) -> Optional[str]:
    """Return the first matching issuer from ISSUER_MAP, or None."""
    lower = combined.lower()
    for pattern, issuer in ISSUER_MAP.items():
        if pattern.lower() in lower:
            return issuer
    return None


def _infer_index_exposure(combined: str) -> Optional[str]:
    """Return index name if name references a specific index, else None."""
    m = re.search(r"EGX\s*(30|70|100)", combined, re.IGNORECASE)
    if m:
        return f"EGX{m.group(1)}"
    if re.search(r"index|مؤشر", combined, re.IGNORECASE):
        return "index"
    return None


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_instrument(
    code: str,
    arabic_name: Optional[str],
    english_name: Optional[str],
    nav_available: bool,
    holdings_available: bool,
    structured_products_codes: set[str],
) -> ClassificationResult:
    """
    Classify one ETP instrument.

    Parameters
    ----------
    code
        EGX ticker/code (uppercase).
    arabic_name
        Arabic display name (may be None).
    english_name
        English display name (may be None).
    nav_available
        True if a NAV record was found for this instrument.
    holdings_available
        True if at least one holdings row was found for this instrument.
    structured_products_codes
        Set of codes found on the EGX Structured Products taxonomy page.

    Returns
    -------
    ClassificationResult
    """
    combined = _combined_name(arabic_name, english_name)
    issuer = _infer_issuer(combined)

    # -----------------------------------------------------------------------
    # Rule 1 — GOLD_ETP (highest specificity — check before ETF)
    # -----------------------------------------------------------------------
    if _GOLD_KW.search(combined):
        return ClassificationResult(
            instrument_type="GOLD_ETP",
            confidence=_HIGH,
            reason="Name contains gold/ذهب/دهب keyword",
            underlying_exposure=_GOLD_EXPOSURE,
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Rule 2 — ETN (explicitly in structured products taxonomy)
    # -----------------------------------------------------------------------
    if code.upper() in structured_products_codes:
        # If it also has holdings it is more likely a standard ETF misclassified
        if not holdings_available and not nav_available:
            return ClassificationResult(
                instrument_type="ETN",
                confidence=_HIGH,
                reason="Code found in structured products taxonomy page",
                underlying_exposure=None,
                issuer=issuer,
            )

    # -----------------------------------------------------------------------
    # Rule 3 — STRUCTURED_NOTE
    # -----------------------------------------------------------------------
    if _STRUCT_KW.search(combined) and not holdings_available:
        return ClassificationResult(
            instrument_type="STRUCTURED_NOTE",
            confidence=_MED,
            reason="Name contains structured/bank/certificate keyword without fund constituents",
            underlying_exposure=None,
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Rule 4 — ETF (has holdings OR NAV — standard collective investment vehicle)
    # -----------------------------------------------------------------------
    if holdings_available and nav_available:
        return ClassificationResult(
            instrument_type="ETF",
            confidence=_HIGH,
            reason="Has fund constituents AND NAV unit data",
            underlying_exposure=_infer_index_exposure(combined),
            issuer=issuer,
        )
    if holdings_available:
        return ClassificationResult(
            instrument_type="ETF",
            confidence=_MED + 0.05,
            reason="Has fund constituents (holdings) data",
            underlying_exposure=_infer_index_exposure(combined),
            issuer=issuer,
        )
    if nav_available:
        # NAV alone is a weaker ETF signal — could be a structured fund
        if _ETF_KW.search(combined):
            return ClassificationResult(
                instrument_type="ETF",
                confidence=_MED + 0.10,
                reason="Has NAV data and name contains ETF/صندوق keyword",
                underlying_exposure=_infer_index_exposure(combined),
                issuer=issuer,
            )
        return ClassificationResult(
            instrument_type="ETF",
            confidence=_MED,
            reason="Has NAV unit data (no holdings found)",
            underlying_exposure=_infer_index_exposure(combined),
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Rule 5 — INDEX_TRACKER (name hints at index tracking, no holdings found)
    # -----------------------------------------------------------------------
    if _INDEX_KW.search(combined):
        return ClassificationResult(
            instrument_type="INDEX_TRACKER",
            confidence=_MED,
            reason="Name references an EGX index but no holdings data found",
            underlying_exposure=_infer_index_exposure(combined),
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Rule 6 — ETN (in structured products, possibly also has nav)
    # -----------------------------------------------------------------------
    if code.upper() in structured_products_codes:
        return ClassificationResult(
            instrument_type="ETN",
            confidence=_MED,
            reason="Code found in structured products taxonomy page (with some data)",
            underlying_exposure=None,
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Rule 7 — Catch-all: name contains ETF keyword but no supporting data
    # -----------------------------------------------------------------------
    if _ETF_KW.search(combined):
        return ClassificationResult(
            instrument_type="ETF",
            confidence=_LOW,
            reason="Name contains ETF/صندوق keyword but no holdings or NAV data found",
            underlying_exposure=_infer_index_exposure(combined),
            issuer=issuer,
        )

    # -----------------------------------------------------------------------
    # Unknown
    # -----------------------------------------------------------------------
    return ClassificationResult(
        instrument_type="UNKNOWN_ETP",
        confidence=_LOW,
        reason="Insufficient evidence to classify",
        underlying_exposure=None,
        issuer=issuer,
    )
