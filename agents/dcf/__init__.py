"""Discounted Cash Flow (DCF) valuation engine for EGX Top-50.

This module provides a standalone weekly DCF pipeline:
- Collects financials via yfinance (with fallbacks)
- Projects free cash flow for 5 years (quarterly)
- Computes a terminal value via Gordon Growth
- Calculates WACC calibrated for Egypt
- Stores results in the database and emits a `dcf_model` signal into the news table

The DCF output is used as a supplementary valuation signal in the existing
multi-agent consensus pipeline.
"""

__all__ = [
    "EgyptDCFConfig",
    "collect_financial_data",
    "run_dcf_pipeline",
    "get_latest_composite_dcf",
]
