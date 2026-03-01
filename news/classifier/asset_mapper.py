"""
news/classifier/asset_mapper.py — Maps classified chunks to EGX/TASI tickers + sectors.

Uses a keyword alias table for direct company name → ticker mapping, and
a sector keyword table for broader sector attribution. Both tables are
intentionally bilingual.

This module is intentionally standalone (no DB access) so it can run
synchronously without I/O overhead. The ticker list is hard-coded here
and should be extended as the universe grows.
"""

from __future__ import annotations

from typing import Dict, List
from news.models import ProcessedChunk


# ── Company name → EGX ticker mapping ────────────────────────────────────────
# Keys: lowercase aliases. Values: Yahoo Finance-style ticker.
# Extend this as coverage grows.

EGX_TICKER_MAP: Dict[str, str] = {
    # Banking
    "cib": "COMI.CA",
    "commercial international bank": "COMI.CA",
    "banque misr": "BMSR.CA",
    "national bank of egypt": "NBED.CA",
    "qnb": "QNBE.CA",
    "housing and development bank": "HDBK.CA",
    "suez canal bank": "CANA.CA",
    "faisal islamic": "FAIT.CA",
    "al baraka": "SAUD.CA",
    "egyptian gulf bank": "EGBE.CA",
    "credit agricole egypt": "CIEB.CA",
    # Financial Services
    "efg hermes": "HRHO.CA",
    "efg": "HRHO.CA",
    "e-finance": "EFIH.CA",
    "fawry": "FWRY.CA",
    "qalaa": "CCAP.CA",
    "b investments": "BINV.CA",
    "ci capital": "CICH.CA",
    "valu": "VALU.CA",
    "raya": "RAYA.CA",
    "contact financial": "CNFN.CA",
    "beltone": "BTFH.CA",
    "orascom financial": "OFH.CA",
    # Real Estate
    "talaat moustafa": "TMGH.CA",
    "tmg": "TMGH.CA",
    "palm hills": "PHDC.CA",
    "sodic": "OCDI.CA",
    "arab real estate": "AMER.CA",
    "orascom development": "ORHD.CA",
    "heliopolis": "HELI.CA",
    "city edge": "CFFE.CA",
    # Telecom
    "orange egypt": "ORTE.CA",
    "telecom egypt": "ETEL.CA",
    "vodafone egypt": "VFCO.CA",
    # Energy / Oil & Gas
    "sidi kerir": "SKPC.CA",
    "egyptian petrochemicals": "EPCO.CA",
    "abou qir": "ABUK.CA",
    # Industrials / Cement
    "suez cement": "SUCE.CA",
    "arabian cement": "ARCC.CA",
    "sinai cement": "SNCE.CA",
    "medco": "MFPC.CA",
    "delta sugar": "DSCF.CA",
    "eastern company": "EAST.CA",
    # Consumer
    "juhayna": "JUFO.CA",
    "edita": "EDIT.CA",
    "cleopatra": "CLHO.CA",
    "misr fertilizers": "MFPC.CA",
    "obour land": "OLFI.CA",
    "universal educational": "UNIV.CA",
    # Diversified
    "six of october": "OCDI.CA",
    "alexandria container": "ALCN.CA",
    "global telecom": "GTHE.CA",
    "orascom telecom": "OTMT.CA",
    "orascom construction": "ORAS.CA",
}

# ── Sector keyword table ──────────────────────────────────────────────────────

SECTOR_MAP: Dict[str, List[str]] = {
    "banking": [
        "bank", "banking", "credit", "deposit", "lending", "loan", "npl",
        "bنك", "مصرف", "ائتمان",
    ],
    "real_estate": [
        "real estate", "property", "developer", "housing", "construction",
        "عقارات", "تطوير عقاري", "مطور",
    ],
    "energy": [
        "oil", "gas", "petroleum", "energy", "refinery", "petrochemical",
        "نفط", "طاقة", "بترول", "مصفاة",
    ],
    "telecom": [
        "telecom", "mobile", "network", "broadband", "5g",
        "اتصالات", "شبكة",
    ],
    "consumer": [
        "retail", "consumer", "food", "beverage", "fmcg", "supermarket",
        "تجزئة", "مستهلك", "غذاء",
    ],
    "industrials": [
        "cement", "steel", "manufacturing", "chemicals", "fertilizer",
        "أسمنت", "صلب", "صناعة", "كيماويات",
    ],
    "financial_services": [
        "leasing", "microfinance", "fintech", "brokerage", "investment bank",
        "تأجير تمويلي", "تمويل",
    ],
    "healthcare": [
        "hospital", "pharmaceutical", "pharma", "healthcare", "medical",
        "مستشفى", "دواء", "صحة",
    ],
    "tourism": [
        "hotel", "tourism", "travel", "resort",
        "فندق", "سياحة",
    ],
}


class AssetMapper:
    """
    Enriches ProcessedChunks with affected_assets and affected_sectors lists.
    Pure computation — no I/O.
    """

    def map_batch(self, chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
        return [self._map_single(chunk) for chunk in chunks]

    def _map_single(self, chunk: ProcessedChunk) -> ProcessedChunk:
        text = (chunk.title + " " + chunk.content).lower()

        for alias, ticker in EGX_TICKER_MAP.items():
            if alias in text and ticker not in chunk.affected_assets:
                chunk.affected_assets.append(ticker)

        for sector, keywords in SECTOR_MAP.items():
            if any(kw in text for kw in keywords) and sector not in chunk.affected_sectors:
                chunk.affected_sectors.append(sector)

        return chunk
