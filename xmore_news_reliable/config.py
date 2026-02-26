"""
config.py — Xmore Reliable News Acquisition Layer
Central configuration. All tuneable values and source definitions live here.
Secrets are loaded from environment / .env — never hardcoded.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

# Load .env from this directory (or project root)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "xmore_news.db")
DOWNLOAD_DIR = BASE_DIR / "downloaded_pdfs"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Gmail OAuth
# ---------------------------------------------------------------------------
GMAIL_SCOPES: List[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]
GMAIL_CREDENTIALS_FILE = BASE_DIR / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
GMAIL_TOKEN_FILE = BASE_DIR / os.getenv("GMAIL_TOKEN_FILE", "token.json")
GMAIL_USER_EMAIL: str = os.getenv("GMAIL_USER_EMAIL", "crassdart@gmail.com")
PROCESSED_LABEL: str = "xmore-processed"


# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------
@dataclass
class EmailSourceConfig:
    """Maps a logical source name to a Gmail label."""
    label: str
    sender_patterns: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class RSSSourceConfig:
    """One or more Google News search queries for this source."""
    queries: List[str]
    max_results: int = 15
    description: str = ""


@dataclass
class PDFSourceConfig:
    """Official page to monitor for new PDF links."""
    page_url: str
    base_url: str
    description: str = ""


# Gmail labels must already exist in crassdart@gmail.com (or be auto-created)
EMAIL_SOURCES: Dict[str, EmailSourceConfig] = {
    "CBE": EmailSourceConfig(
        label="CBE",
        sender_patterns=["@cbe.org.eg", "centralbank.eg"],
        description="Central Bank of Egypt official communications",
    ),
    "IMF": EmailSourceConfig(
        label="IMF",
        sender_patterns=["@imf.org"],
        description="IMF press releases and Egypt program updates",
    ),
    "EGX": EmailSourceConfig(
        label="EGX",
        sender_patterns=["@egx.com.eg", "egyptianexchange"],
        description="Egyptian Exchange corporate disclosures",
    ),
    "Enterprise": EmailSourceConfig(
        label="Enterprise",
        sender_patterns=["@enterprise.press", "@enterprisemea.com", "enterprisenewsroom"],
        description="Enterprise Egypt daily briefings",
    ),
}

RSS_SOURCES: Dict[str, RSSSourceConfig] = {
    "CBE": RSSSourceConfig(
        queries=[
            "Central Bank of Egypt monetary policy interest rate",
            "CBE Egypt inflation currency",
        ],
        max_results=15,
        description="CBE policy decisions via Google News",
    ),
    "IMF": RSSSourceConfig(
        queries=[
            "IMF Egypt loan program review",
            "International Monetary Fund Egypt 2025",
        ],
        max_results=10,
        description="IMF Egypt program news",
    ),
    "EGX": RSSSourceConfig(
        queries=[
            "Egyptian Exchange EGX earnings disclosure",
            "Egypt stock market EGX30",
            "Egypt corporate results dividend",
        ],
        max_results=20,
        description="EGX market and earnings news",
    ),
    "Ministry_Finance": RSSSourceConfig(
        queries=[
            "Ministry of Finance Egypt budget deficit",
            "Egypt Treasury bonds T-bills yield",
        ],
        max_results=10,
        description="Egyptian fiscal policy news",
    ),
    "Enterprise": RSSSourceConfig(
        queries=[
            "Enterprise Egypt business news",
            "Egypt economy macro 2025",
        ],
        max_results=15,
        description="Enterprise Egypt business coverage",
    ),
    "FRA": RSSSourceConfig(
        queries=[
            "FRA Egypt Financial Regulatory Authority decision",
            "Egypt capital markets regulation",
        ],
        max_results=10,
        description="FRA regulatory decisions",
    ),
    "AlArabiya_Egypt": RSSSourceConfig(
        queries=[
            "site:alarabiya.net اقتصاد مصر بورصة",
            "Al Arabiya Egypt economy EGX stock market",
        ],
        max_results=15,
        description="Al Arabiya Egypt economy coverage (alarabiya.net — direct access blocked, via Google News)",
    ),
    "CNN_Arabic_Egypt": RSSSourceConfig(
        queries=[
            "site:arabic.cnn.com الاقتصاد المصري",
            "CNN Arabic Egypt economy inflation GDP",
        ],
        max_results=15,
        description="CNN Arabic Egypt economy tag (arabic.cnn.com/tag/alaqtsad-almsry)",
    ),
    "Asharq_Business_Egypt": RSSSourceConfig(
        queries=[
            "site:asharqbusiness.com مصر اقتصاد",
            "Asharq Business Egypt economy investments",
        ],
        max_results=15,
        description="Asharq Business Egypt coverage (asharqbusiness.com/tags/36 — Cloudflare blocked, via Google News)",
    ),
    "CBE_Arabic_News": RSSSourceConfig(
        queries=[
            "البنك المركزي المصري بيان قرار",
            "CBE Egypt central bank decision press release",
        ],
        max_results=10,
        description="CBE Arabic news page (cbe.org.eg/ar/news-publications/news — WAF blocked, via Google News)",
    ),
    "EIP_IDSC": RSSSourceConfig(
        queries=[
            "مركز المعلومات ودعم اتخاذ القرار مصر اقتصاد",
            "IDSC Egypt economic information decision support",
        ],
        max_results=10,
        description="EIP/IDSC Egypt government economic news (eip.gov.eg/IDSC/News)",
    ),
    "AlBorsa_News": RSSSourceConfig(
        queries=[
            "site:alborsaanews.com بورصة مصر",
            "Al Borsa News Egypt stocks EGX",
        ],
        max_results=20,
        description="Al Borsa News — EGX stocks & companies (has direct RSS at alborsaanews.com/feed)",
    ),
    "AlMal_News": RSSSourceConfig(
        queries=[
            "site:almalnews.com بورصة أسهم مصر",
            "Al Mal News Egypt stocks market",
        ],
        max_results=15,
        description="Al Mal News Egypt stocks category (almalnews.com/category/stocks — no RSS, via Google News)",
    ),
    "Investing_Egypt": RSSSourceConfig(
        queries=[
            "site:sa.investing.com Egypt equities stocks",
            "Investing.com Egypt EGX market analysis",
        ],
        max_results=10,
        description="Investing.com Egypt equities (sa.investing.com/equities/egypt — 403 blocked, via Google News)",
    ),
    "EGX_Arabic": RSSSourceConfig(
        queries=[
            "site:egx.com.eg بورصة مصر إعلانات",
            "EGX Egyptian Exchange Arabic announcements disclosures",
        ],
        max_results=10,
        description="EGX Arabic pages (egx.com.eg/ar — JS-rendered, via Google News)",
    ),
}

PDF_SOURCES: Dict[str, PDFSourceConfig] = {
    "EGX_disclosure": PDFSourceConfig(
        page_url="https://www.egx.com.eg/en/disclosures.aspx",
        base_url="https://www.egx.com.eg",
        description="EGX corporate disclosure PDFs",
    ),
    "CBE_publications": PDFSourceConfig(
        page_url="https://www.cbe.org.eg/en/monetary-policy",
        base_url="https://www.cbe.org.eg",
        description="CBE monetary policy decision PDFs",
    ),
    "FRA_decisions": PDFSourceConfig(
        page_url="https://www.fra.gov.eg/content/fra/ar/DecisionsList.html",
        base_url="https://www.fra.gov.eg",
        description="FRA regulatory decision PDFs",
    ),
    "Ministry_Finance_reports": PDFSourceConfig(
        page_url="https://www.mof.gov.eg/en/reports",
        base_url="https://www.mof.gov.eg",
        description="Ministry of Finance economic reports",
    ),
}

# ---------------------------------------------------------------------------
# Rate limits & thresholds
# ---------------------------------------------------------------------------
RSS_RATE_LIMIT_SECONDS: int = int(os.getenv("RSS_RATE_LIMIT_SECONDS", "30"))
PDF_CHECK_INTERVAL_SECONDS: int = int(os.getenv("PDF_CHECK_INTERVAL_SECONDS", "3600"))
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "30"))
PDF_DOWNLOAD_TIMEOUT: int = int(os.getenv("PDF_DOWNLOAD_TIMEOUT", "60"))

# Health monitoring thresholds
HEALTH_DEGRADED_THRESHOLD: int = 3   # consecutive failures → degraded
HEALTH_OFFLINE_HOURS: int = 24        # hours without success → offline

# EGX-listed ticker symbols (used for entity detection across all articles)
EGX_TICKERS: List[str] = [
    "COMI", "EKHW", "EGTS", "HRHO", "OCDI", "PHDC", "CLHO", "GBCO", "FWRY",
    "SWDY", "TELE", "MFPC", "MNHD", "ORWE", "SPMD", "TMGH", "CIEB", "ADIB",
    "DCRC", "ISPH", "AMOC", "SOCO", "BICO", "DICE", "RAYA", "JUFO", "EKHO",
    "INCO", "AMER", "MCQE", "CIRA", "SUGR", "HELI", "LCSW", "EFIC",
]
