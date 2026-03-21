"""
validate_ksa_setup.py
=====================
Validates that the KSA branch is correctly set up before the first pipeline run.

Usage:
    python validation/validate_ksa_setup.py
    python validation/validate_ksa_setup.py --verbose
    python validation/validate_ksa_setup.py --fix          # auto-fix minor issues

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from typing import Callable

# ── Ensure the project root is on sys.path ──────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS  = "PASS"
FAIL  = "FAIL"
WARN  = "WARN"
SKIP  = "SKIP"

_results: list[tuple[str, str, str]] = []   # (check_name, status, message)
_verbose = False


def _log(check: str, status: str, msg: str) -> None:
    _results.append((check, status, msg))
    icon = {"PASS": "OK", "FAIL": "FAIL", "WARN": "WARN", "SKIP": "SKIP"}.get(status, "??")
    color = {
        "PASS": "\033[92m",
        "FAIL": "\033[91m",
        "WARN": "\033[93m",
        "SKIP": "\033[94m",
    }.get(status, "")
    reset = "\033[0m"
    print(f"  [{color}{icon}{reset}] {check}: {msg}")


# =============================================================================
# Check 1 — Universe file integrity
# =============================================================================

def check_ksa_universe() -> None:
    """Validate config/ksa_universe.py loads correctly and has 50 stocks."""
    check = "KSA Universe"
    try:
        from config.ksa_universe import (
            KSA_TOP50,
            KSA_INITIAL_UNIVERSE,
            KSA_SECTOR_MAP,
            KSA_MT30_TICKERS,
            KSA_BANKING_TICKERS,
        )
    except ImportError as exc:
        _log(check, FAIL, f"Import failed: {exc}")
        return

    # Count — allow 50+ (list may include extra valid tickers)
    if len(KSA_TOP50) < 50:
        _log(check, FAIL, f"Expected at least 50 stocks in KSA_TOP50, got {len(KSA_TOP50)}")
        return

    # Symbol format
    bad_symbols = [s["symbol"] for s in KSA_TOP50 if not s["symbol"].endswith(".SR")]
    if bad_symbols:
        _log(check, FAIL, f"Symbols missing .SR suffix: {bad_symbols[:5]}")
        return

    # Required keys in each entry
    required_keys = {"symbol", "name_en", "name_ar", "sector_en", "sector_ar"}
    for stock in KSA_TOP50:
        missing = required_keys - stock.keys()
        if missing:
            _log(check, FAIL, f"{stock.get('symbol','?')} missing keys: {missing}")
            return

    # MT30 subset check
    universe_set = set(KSA_INITIAL_UNIVERSE)
    mt30_outside = [s for s in KSA_MT30_TICKERS if s not in universe_set]
    if mt30_outside:
        _log(check, WARN, f"MT30 tickers not in KSA_TOP50: {mt30_outside}")
    else:
        _log(check, PASS, f"50 stocks, {len(KSA_MT30_TICKERS)} MT30, {len(KSA_BANKING_TICKERS)} banking, {len(KSA_SECTOR_MAP)} sectors")


# =============================================================================
# Check 2 — DCF config integrity
# =============================================================================

def check_ksa_dcf_config() -> None:
    """Validate agents/dcf/ksa_dcf_config.py loads and has required attributes."""
    check = "KSA DCF Config"
    try:
        from agents.dcf import ksa_dcf_config as cfg
    except ImportError as exc:
        _log(check, FAIL, f"Import failed: {exc}")
        return

    required_attrs = [
        "KSA_RISK_FREE_RATE",
        "KSA_EQUITY_RISK_PREMIUM",
        "KSA_TAX_RATE",
        "KSA_TERMINAL_GROWTH_RATE",
        "KSA_FORECAST_YEARS",
        "KSA_SECTOR_WACC_OVERRIDES",
        "KSA_SECTOR_TERMINAL_GROWTH",
        "KSA_SECTOR_DEFAULT_BETA",
        "KSA_DCF_SCENARIOS",
        "KSA_DATA_SOURCES",
        "KSA_YFINANCE_SUFFIX",
        "KSA_TRADING_DAYS_PER_YEAR",
    ]
    missing = [a for a in required_attrs if not hasattr(cfg, a)]
    if missing:
        _log(check, FAIL, f"Missing attributes: {missing}")
        return

    # Sanity checks on values
    errors = []
    if not (0 < cfg.KSA_RISK_FREE_RATE < 0.20):
        errors.append(f"KSA_RISK_FREE_RATE={cfg.KSA_RISK_FREE_RATE} out of expected range")
    if not (0 < cfg.KSA_EQUITY_RISK_PREMIUM < 0.20):
        errors.append(f"KSA_EQUITY_RISK_PREMIUM={cfg.KSA_EQUITY_RISK_PREMIUM} out of range")
    if not (0 < cfg.KSA_TAX_RATE <= 0.50):
        errors.append(f"KSA_TAX_RATE={cfg.KSA_TAX_RATE} out of range")
    if cfg.KSA_YFINANCE_SUFFIX != ".SR":
        errors.append(f"KSA_YFINANCE_SUFFIX expected '.SR', got '{cfg.KSA_YFINANCE_SUFFIX}'")
    if cfg.KSA_FORECAST_YEARS < 1:
        errors.append("KSA_FORECAST_YEARS must be >= 1")
    if errors:
        _log(check, FAIL, "; ".join(errors))
        return

    _log(check, PASS,
         f"RFR={cfg.KSA_RISK_FREE_RATE:.2%}, ERP={cfg.KSA_EQUITY_RISK_PREMIUM:.2%}, "
         f"Tax={cfg.KSA_TAX_RATE:.0%}, Suffix='{cfg.KSA_YFINANCE_SUFFIX}'")


# =============================================================================
# Check 3 — Database schema SQL file
# =============================================================================

def check_ksa_schema_sql() -> None:
    """Validate db/migrations/ksa_schema.sql exists and contains expected tables."""
    check = "KSA Schema SQL"
    sql_path = PROJECT_ROOT / "db" / "migrations" / "ksa_schema.sql"

    if not sql_path.exists():
        _log(check, FAIL, f"File not found: {sql_path}")
        return

    content = sql_path.read_text(encoding="utf-8")

    expected_tables = [
        "ksa_stocks",
        "ksa_prices",
        "ksa_trade_recommendations",
        "ksa_signal_evaluations",
        "ksa_dcf_results",
        "ksa_regime_log",
        "ksa_news_sentiment",
    ]
    missing_tables = [t for t in expected_tables if f"CREATE TABLE IF NOT EXISTS {t}" not in content]
    if missing_tables:
        _log(check, FAIL, f"Missing CREATE TABLE statements for: {missing_tables}")
        return

    # Check ALTER TABLE for market column extension
    if "ALTER TABLE egx30_stocks" not in content:
        _log(check, WARN, "ALTER TABLE egx30_stocks not found — cross-market extension may be missing")
    else:
        _log(check, PASS, f"{len(expected_tables)} tables defined, ALTER TABLE egx30_stocks present")


# =============================================================================
# Check 4 — Render KSA YAML
# =============================================================================

def check_render_ksa_yaml() -> None:
    """Validate render-ksa.yaml exists and has required KSA-specific keys."""
    check = "render-ksa.yaml"
    yaml_path = PROJECT_ROOT / "render-ksa.yaml"

    if not yaml_path.exists():
        _log(check, FAIL, f"File not found: {yaml_path}")
        return

    content = yaml_path.read_text(encoding="utf-8")

    required_strings = [
        "xmore-ksa-dashboard",
        "ksa-trading-db",
        "ksa_trading_system",
        "MARKET",
        "KSA",
        "SAR",
    ]
    missing = [s for s in required_strings if s not in content]
    if missing:
        _log(check, FAIL, f"Missing required content: {missing}")
        return

    # Must NOT reference the EGX database name
    if "trading_system" in content and "ksa_trading_system" not in content:
        _log(check, WARN, "render-ksa.yaml may reference EGX database — double-check DB names")
    else:
        _log(check, PASS, "Service name, database name, MARKET=KSA, currency=SAR all present")


# =============================================================================
# Check 5 — Python package imports for KSA pipeline
# =============================================================================

def check_python_dependencies() -> None:
    """Check that key Python dependencies required by the KSA pipeline are importable."""
    check = "Python Dependencies"

    # (module_name, pip_package, required_for_ksa)
    deps: list[tuple[str, str, bool]] = [
        ("lightgbm",   "lightgbm>=4.3.0",   False),   # optional locally; required in CI via requirements.txt
        ("pandas",     "pandas",             True),
        ("numpy",      "numpy",              True),
        ("sklearn",    "scikit-learn",       True),
        ("sqlalchemy", "sqlalchemy",         False),
        ("requests",   "requests",           True),
        ("optuna",     "optuna",             False),
        ("hmmlearn",   "hmmlearn",           False),
        ("arch",       "arch",               False),
    ]

    missing_required: list[str] = []
    missing_optional: list[str] = []

    for module, package, required in deps:
        spec = importlib.util.find_spec(module)  # type: ignore[attr-defined]
        if spec is None:
            if required:
                missing_required.append(package)
            else:
                missing_optional.append(package)

    if missing_required:
        _log(check, FAIL, f"Missing required packages: {missing_required}")
    elif missing_optional:
        _log(check, WARN, f"Optional packages not installed (non-fatal): {missing_optional}")
    else:
        _log(check, PASS, "All required Python dependencies importable")


# =============================================================================
# Check 6 — Environment variables for KSA pipeline
# =============================================================================

def check_environment_variables() -> None:
    """Check that required environment variables are present (warns if missing)."""
    check = "Environment Variables"

    required_vars = ["DATABASE_URL"]
    recommended_vars = [
        "GOOGLE_API_KEY",
        "NEWS_API_KEY",
        "FINNHUB_API_KEY",
        "ARGAAM_API_KEY",
        "MARKET",
    ]

    missing_required   = [v for v in required_vars   if not os.environ.get(v)]
    missing_recommended = [v for v in recommended_vars if not os.environ.get(v)]

    market = os.environ.get("MARKET", "")
    if market and market != "KSA":
        _log(check, WARN, f"MARKET env var is '{market}', expected 'KSA' for this branch")
        return

    if missing_required:
        _log(check, WARN, f"Required env vars not set: {missing_required} (OK for local dev without DB)")
    elif missing_recommended:
        _log(check, WARN, f"Recommended env vars not set: {missing_recommended}")
    else:
        _log(check, PASS, "All required and recommended env vars present")


# =============================================================================
# Main runner
# =============================================================================

CHECKS: list[tuple[str, Callable[[], None]]] = [
    ("Universe",          check_ksa_universe),
    ("DCF Config",        check_ksa_dcf_config),
    ("Schema SQL",        check_ksa_schema_sql),
    ("Render YAML",       check_render_ksa_yaml),
    ("Python Deps",       check_python_dependencies),
    ("Env Vars",          check_environment_variables),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate KSA branch setup")
    parser.add_argument("--verbose", action="store_true", help="Show extra detail")
    parser.add_argument("--fix",     action="store_true", help="Auto-fix minor issues (reserved)")
    args = parser.parse_args()

    global _verbose
    _verbose = args.verbose

    print()
    print("=" * 60)
    print("  Xmore KSA — Setup Validation")
    print(f"  Project root: {PROJECT_ROOT}")
    print("=" * 60)
    print()

    for _label, fn in CHECKS:
        fn()

    print()
    print("=" * 60)
    passed  = sum(1 for _, s, _ in _results if s == PASS)
    warned  = sum(1 for _, s, _ in _results if s == WARN)
    failed  = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)

    print(f"  Results: {passed} passed, {warned} warnings, {failed} failed, {skipped} skipped")
    print("=" * 60)
    print()

    if failed:
        print("  ACTION REQUIRED: Fix the FAIL items above before running the KSA pipeline.")
        return 1

    if warned:
        print("  Setup looks good — review the WARN items above when convenient.")
    else:
        print("  All checks passed. KSA branch is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
