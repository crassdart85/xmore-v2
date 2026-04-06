"""Financial data collection for DCF valuation.

Fetches historical financials (cash flow, income, balance sheet) using yfinance
and returns a normalized dataset suitable for DCF projection.

If certain data is missing, the collector falls back to sector defaults.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


def collect_financial_data(ticker_ca: str, ticker_yahoo: str, sector: str) -> dict:
    """Collects financial data required for DCF valuation.

    Args:
        ticker_ca: EGX CA ticker (e.g., COMI)
        ticker_yahoo: yfinance ticker (e.g., 2222.SR)
        sector: sector name used for defaults/assumptions

    Returns:
        dict with financial history, current market data, and data quality flags.
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError("yfinance is required for DCF data collection") from e

    result = {
        "ticker": ticker_ca,
        "sector": sector,
        "data_quality": {
            "has_cashflow": False,
            "has_income": False,
            "has_balance": False,
            "years_available": 0,
            "confidence": "LOW",
        },
        # Income statement
        "revenue_history": [],
        "ebitda_history": [],
        "net_income_history": [],
        "revenue_growth_avg": None,
        # Cash flow
        "operating_cf_history": [],
        "capex_history": [],
        "fcf_history": [],
        "fcf_margin_avg": None,
        # Balance sheet
        "total_debt": None,
        "cash_and_equivalents": None,
        "shares_outstanding": None,
        # Valuation inputs
        "current_price": None,
        "market_cap": None,
        "beta": None,
        "tax_rate": 0.225,  # Egypt corporate tax 22.5%
    }

    try:
        stock = yf.Ticker(ticker_yahoo)
        # yfinance is rate-limited; be polite.
        time.sleep(1.5)
        info = stock.info or {}

        result["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["market_cap"] = info.get("marketCap")
        result["beta"] = info.get("beta") or 1.0
        result["shares_outstanding"] = info.get("sharesOutstanding")

        # Cash flow (annual)
        try:
            cf = stock.cashflow
            if cf is not None and not cf.empty:
                result["data_quality"]["has_cashflow"] = True
                for col in cf.columns:
                    year = col.year
                    ocf = _safe_get(cf, "Operating Cash Flow", col) or _safe_get(cf, "Total Cash From Operating Activities", col)
                    cap = _safe_get(cf, "Capital Expenditure", col) or _safe_get(cf, "Purchase Of Property Plant And Equipment", col)
                    if ocf is not None:
                        fcf = ocf + (cap or 0)
                        result["operating_cf_history"].append({"year": year, "ocf": ocf})
                        result["capex_history"].append({"year": year, "capex": cap or 0})
                        result["fcf_history"].append({"year": year, "fcf": fcf})
        except Exception as e:
            logger.debug(f"[DCF:{ticker_ca}] cashflow load failed: {e}")

        # Income statement (annual)
        try:
            inc = stock.financials
            if inc is not None and not inc.empty:
                result["data_quality"]["has_income"] = True
                for col in inc.columns:
                    year = col.year
                    revenue = _safe_get(inc, "Total Revenue", col)
                    ebitda = _safe_get(inc, "EBITDA", col) or _safe_get(inc, "Normalized EBITDA", col)
                    ni = _safe_get(inc, "Net Income", col)
                    if revenue:
                        result["revenue_history"].append({"year": year, "revenue": revenue})
                    if ebitda:
                        result["ebitda_history"].append({"year": year, "ebitda": ebitda})
                    if ni:
                        result["net_income_history"].append({"year": year, "net_income": ni})
        except Exception as e:
            logger.debug(f"[DCF:{ticker_ca}] income statement load failed: {e}")

        # Balance sheet (most recent)
        try:
            bs = stock.balance_sheet
            if bs is not None and not bs.empty:
                result["data_quality"]["has_balance"] = True
                latest = bs.columns[0]
                result["total_debt"] = (_safe_get(bs, "Total Debt", latest) or
                                         _safe_get(bs, "Long Term Debt", latest) or 0)
                result["cash_and_equivalents"] = (_safe_get(bs, "Cash And Cash Equivalents", latest) or
                                                   _safe_get(bs, "Cash Cash Equivalents And Short Term Investments", latest) or 0)
        except Exception as e:
            logger.debug(f"[DCF:{ticker_ca}] balance sheet load failed: {e}")

        # Derive quality metrics
        years = len(result["revenue_history"])
        result["data_quality"]["years_available"] = years
        result["data_quality"]["confidence"] = (
            "HIGH" if years >= 4 else
            "MEDIUM" if years >= 2 else
            "LOW"
        )

        # Revenue growth
        if len(result["revenue_history"]) >= 2:
            revs = sorted(result["revenue_history"], key=lambda x: x["year"])
            growths = [
                (revs[i]["revenue"] - revs[i - 1]["revenue"]) / revs[i - 1]["revenue"]
                for i in range(1, len(revs))
                if revs[i - 1]["revenue"]
            ]
            result["revenue_growth_avg"] = sum(growths) / len(growths) if growths else None

        # FCF margin average
        if result["fcf_history"] and result["revenue_history"]:
            rev_map = {r["year"]: r["revenue"] for r in result["revenue_history"]}
            margins = [
                f["fcf"] / rev_map[f["year"]]
                for f in result["fcf_history"]
                if f["year"] in rev_map and rev_map[f["year"]]
            ]
            result["fcf_margin_avg"] = sum(margins) / len(margins) if margins else None

    except Exception as e:
        logger.error(f"[DCF:{ticker_ca}] data collection failed: {e}")

    return result


def _safe_get(df: pd.DataFrame, row_name: str, col) -> Optional[float]:
    """Safely fetch a value from a yfinance DataFrame by row label."""
    try:
        for idx in df.index:
            if row_name.lower() in str(idx).lower():
                val = df.loc[idx, col]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return None
                return float(val)
    except Exception:
        return None
