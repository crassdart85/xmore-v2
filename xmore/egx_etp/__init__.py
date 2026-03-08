"""
xmore.egx_etp
~~~~~~~~~~~~~
EGX ETP ingestion package.

Discovers, classifies, and stores the full live EGX ETP universe
(ETFs, structured products, index-tracking funds, gold-linked ETPs,
certificates).

Quick start::

    from xmore.egx_etp import run_daily
    summary = run_daily()

See README.md for full documentation.
"""

from xmore.egx_etp.pipeline import run_daily
from xmore.egx_etp.models import ProductCard, HoldingRow, ClassificationResult

__all__ = ["run_daily", "ProductCard", "HoldingRow", "ClassificationResult"]
