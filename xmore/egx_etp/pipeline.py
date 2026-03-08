"""
xmore.egx_etp.pipeline
~~~~~~~~~~~~~~~~~~~~~~~
Main orchestrator for daily EGX ETP ingestion.

Usage
-----
Run as a module::

    python -m xmore.egx_etp.pipeline

Or import and call::

    from xmore.egx_etp.pipeline import run_daily
    summary = run_daily()

Steps
-----
1.  Start scrape_run_log entry
2.  Fetch + archive all EGX pages
3.  Parse trading page → product cards
4.  Parse holdings page → holding rows (grouped by fund_code)
5.  Parse NAV page → nav records (keyed by fund_code)
6.  Parse fund volume page → volume records (keyed by fund_code)
7.  Fetch + parse structured products page for taxonomy (set of codes)
8.  For each product card: classify → upsert_product → insert_market_snapshot
9.  Insert holdings for matched products
10. Finish run log
11. Save summary JSON to ./raw_pages/run_YYYYMMDD.json
12. Print JSON summary to stdout
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging setup (done before any local imports so sub-modules inherit it)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local imports (after logging setup)
# ---------------------------------------------------------------------------

from xmore.egx_etp import classifier as clf_module
from xmore.egx_etp import db, fetcher, parser
from xmore.egx_etp.models import HoldingRow, NavRecord, ProductCard, VolumeRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_DIR = Path(os.environ.get("RAW_DIR", "./raw_pages"))

_EGX_URLS: Dict[str, str] = {
    "trading":     "https://www.egx.com.eg/en/ETFSPr.aspx",
    "holdings":    "https://www.egx.com.eg/en/FundConstituents.aspx",
    "nav":         "https://www.egx.com.eg/en/NavUnit.aspx",
    "volume":      "https://www.egx.com.eg/en/EtfFundVolume.aspx",
    "distribution":"https://www.egx.com.eg/en/funddistribution.aspx",
    "bonds":       "https://www.egx.com.eg/en/ListedBonds.aspx",
    "structured":  "https://www.egx.com.eg/en/Structured_products.aspx",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_and_archive(conn, page_key: str, url: str) -> Optional[str]:
    """
    Fetch one URL, archive raw HTML, record in DB, return html text.

    Returns None on unrecoverable failure (already logged).
    """
    try:
        html, method = fetcher.fetch_html(url)
        body_path = fetcher.archive_raw(url, method, html)
        db.record_archive(conn, url, method, body_path)
        return html
    except Exception as exc:
        logger.error("Failed to fetch %s (%s): %s", page_key, url, exc)
        return None


def _group_holdings(rows: List[HoldingRow]) -> Dict[str, List[HoldingRow]]:
    """Return dict mapping fund_code → list[HoldingRow]."""
    grouped: Dict[str, List[HoldingRow]] = defaultdict(list)
    for r in rows:
        grouped[r.fund_code].append(r)
    return grouped


def _index_nav(records: List[NavRecord]) -> Dict[str, NavRecord]:
    """Return dict mapping fund_code → latest NavRecord."""
    idx: Dict[str, NavRecord] = {}
    for r in records:
        # If duplicate codes, keep the one with a non-None value
        existing = idx.get(r.fund_code)
        if existing is None or (r.nav_value is not None and existing.nav_value is None):
            idx[r.fund_code] = r
    return idx


def _index_volume(records: List[VolumeRecord]) -> Dict[str, VolumeRecord]:
    """Return dict mapping fund_code → latest VolumeRecord."""
    idx: Dict[str, VolumeRecord] = {}
    for r in records:
        existing = idx.get(r.fund_code)
        if existing is None or (r.volume is not None and existing.volume is None):
            idx[r.fund_code] = r
    return idx


def _enrich_card_nav(card: ProductCard, nav_idx: Dict[str, NavRecord]) -> ProductCard:
    """Fill card.nav_value from NAV index if not already set."""
    if card.nav_value is None and card.code in nav_idx:
        nr = nav_idx[card.code]
        return ProductCard(
            code=card.code,
            arabic_name=card.arabic_name,
            english_name=card.english_name,
            close_price=card.close_price,
            change_pct=card.change_pct,
            nav_value=nr.nav_value,
            prem_disc=card.prem_disc,
            source_url=card.source_url,
            raw_text=card.raw_text,
        )
    return card


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_daily(run_type: str = "incremental") -> Dict[str, Any]:
    """
    Run the full daily EGX ETP ingestion pipeline.

    Parameters
    ----------
    run_type
        ``'incremental'`` (default) or ``'backfill'``

    Returns
    -------
    dict
        Summary with keys: run_id, status, cards_found, holdings_rows,
        nav_rows, volume_rows, products_upserted, errors.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    conn = db.get_connection()
    db.ensure_schema(conn)

    run_id = db.log_run(conn, run_type=run_type)
    logger.info("=== EGX ETP Pipeline started | run_id=%d run_type=%s ===", run_id, run_type)

    today_str = date.today().isoformat()
    errors: List[str] = []
    stats: Dict[str, Any] = {
        "run_id": run_id,
        "run_type": run_type,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cards_found": 0,
        "holdings_rows": 0,
        "nav_rows": 0,
        "volume_rows": 0,
        "products_upserted": 0,
        "errors": errors,
        "status": "running",
    }

    try:
        # ------------------------------------------------------------------
        # Step 2 — Fetch all pages
        # ------------------------------------------------------------------
        logger.info("Fetching EGX pages…")
        raw: Dict[str, Optional[str]] = {}
        for key, url in _EGX_URLS.items():
            raw[key] = _fetch_and_archive(conn, key, url)

        # ------------------------------------------------------------------
        # Step 3 — Parse trading page → product cards
        # ------------------------------------------------------------------
        cards: List[ProductCard] = []
        if raw["trading"]:
            try:
                cards = parser.parse_trading_page(raw["trading"], _EGX_URLS["trading"])
            except Exception as exc:
                msg = f"parse_trading_page failed: {exc}"
                logger.error(msg)
                errors.append(msg)
        stats["cards_found"] = len(cards)

        # ------------------------------------------------------------------
        # Step 4 — Parse holdings page
        # ------------------------------------------------------------------
        holding_rows: List[HoldingRow] = []
        if raw["holdings"]:
            try:
                holding_rows = parser.parse_holdings_page(raw["holdings"])
            except Exception as exc:
                msg = f"parse_holdings_page failed: {exc}"
                logger.error(msg)
                errors.append(msg)
        stats["holdings_rows"] = len(holding_rows)
        holdings_by_code = _group_holdings(holding_rows)

        # ------------------------------------------------------------------
        # Step 5 — Parse NAV page
        # ------------------------------------------------------------------
        nav_records: List[NavRecord] = []
        if raw["nav"]:
            try:
                nav_records = parser.parse_nav_page(raw["nav"])
            except Exception as exc:
                msg = f"parse_nav_page failed: {exc}"
                logger.error(msg)
                errors.append(msg)
        stats["nav_rows"] = len(nav_records)
        nav_by_code = _index_nav(nav_records)

        # ------------------------------------------------------------------
        # Step 6 — Parse fund volume page
        # ------------------------------------------------------------------
        vol_records: List[VolumeRecord] = []
        if raw["volume"]:
            try:
                vol_records = parser.parse_fund_volume_page(raw["volume"])
            except Exception as exc:
                msg = f"parse_fund_volume_page failed: {exc}"
                logger.error(msg)
                errors.append(msg)
        stats["volume_rows"] = len(vol_records)
        vol_by_code = _index_volume(vol_records)

        # ------------------------------------------------------------------
        # Step 7 — Structured products taxonomy
        # ------------------------------------------------------------------
        structured_codes: set[str] = set()
        if raw["structured"]:
            try:
                sp_list = parser.parse_structured_products(raw["structured"])
                structured_codes = {d["code"] for d in sp_list if d.get("code")}
                logger.info("Structured products taxonomy: %d codes", len(structured_codes))
            except Exception as exc:
                msg = f"parse_structured_products failed: {exc}"
                logger.error(msg)
                errors.append(msg)

        # ------------------------------------------------------------------
        # Step 8 — Process each card: classify + upsert + snapshot
        # ------------------------------------------------------------------
        products_upserted = 0
        for card in cards:
            try:
                # Enrich card with NAV from dedicated NAV page if missing
                card = _enrich_card_nav(card, nav_by_code)

                nav_avail = (
                    card.nav_value is not None
                    or card.code in nav_by_code
                )
                holdings_avail = card.code in holdings_by_code

                classification = clf_module.classify_instrument(
                    code=card.code,
                    arabic_name=card.arabic_name,
                    english_name=card.english_name,
                    nav_available=nav_avail,
                    holdings_available=holdings_avail,
                    structured_products_codes=structured_codes,
                )

                logger.debug(
                    "Card %s → %s (%.2f) | %s",
                    card.code,
                    classification.instrument_type,
                    classification.confidence,
                    classification.reason,
                )

                etp_id = db.upsert_product(conn, card, classification)

                vol_rec = vol_by_code.get(card.code)
                db.insert_market_snapshot(conn, etp_id, card, vol_rec)

                # ----------------------------------------------------------
                # Step 9 — Holdings for this card
                # ----------------------------------------------------------
                if holdings_avail:
                    card_holdings = holdings_by_code[card.code]
                    db.insert_holdings(conn, etp_id, card_holdings, today_str)

                products_upserted += 1

            except Exception as exc:
                msg = f"Error processing card {card.code}: {exc}"
                logger.error(msg, exc_info=True)
                errors.append(msg)
                # Continue — do not let one product crash the whole run

        stats["products_upserted"] = products_upserted

        # ------------------------------------------------------------------
        # Step 10 — Finish run log
        # ------------------------------------------------------------------
        final_status = "failed" if (not cards and errors) else "success"
        stats["status"] = final_status
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        stats["errors"] = errors

        error_str = "; ".join(errors) if errors else None
        db.finish_run(conn, run_id, final_status, stats, error=error_str)

    except Exception as exc:
        msg = f"Pipeline-level failure: {exc}"
        logger.critical(msg, exc_info=True)
        errors.append(msg)
        stats["status"] = "failed"
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        stats["errors"] = errors
        try:
            db.finish_run(conn, run_id, "failed", stats, error=msg)
        except Exception:
            pass
        raise

    finally:
        try:
            conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Step 11 — Save summary JSON
    # ------------------------------------------------------------------
    summary_path = RAW_DIR / f"run_{today_str}.json"
    try:
        summary_path.write_text(
            json.dumps(stats, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.info("Summary saved to %s", summary_path)
    except Exception as exc:
        logger.warning("Could not save summary JSON: %s", exc)

    # ------------------------------------------------------------------
    # Step 12 — Print JSON summary to stdout
    # ------------------------------------------------------------------
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

    logger.info(
        "=== Pipeline complete | status=%s cards=%d upserted=%d errors=%d ===",
        stats["status"], stats["cards_found"], stats["products_upserted"], len(errors),
    )

    return stats


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="EGX ETP daily ingestion pipeline")
    ap.add_argument(
        "--run-type",
        choices=["incremental", "backfill"],
        default="incremental",
        help="Run type (default: incremental)",
    )
    args = ap.parse_args()

    summary = run_daily(run_type=args.run_type)
    sys.exit(0 if summary.get("status") == "success" else 1)
