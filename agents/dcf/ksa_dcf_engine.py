"""
KSA DCF Valuation Engine — Saudi Exchange multi-scenario DCF with DDM for banks.

Valuation approach:
  Non-banking: 3-stage DCF (explicit 5yr FCF + fade + terminal)
  Banking:     Dividend Discount Model P = D1 / (Ke - g)
  Both:        3 scenarios (bull/base/bear) with scenario-weighted intrinsic value

All prices in SAR. market_id = 'KSA'.
"""
import logging
import os
from datetime import datetime
from typing import Optional
import json

logger = logging.getLogger(__name__)

from agents.dcf.ksa_dcf_config import KSA_DCF_CONFIG
from config.ksa_universe import KSA_TOP50, KSA_BANKING_TICKERS, KSA_SECTOR_MAP


# ── WACC calculation ─────────────────────────────────────────────────────────

def _calc_wacc(beta: float, debt_ratio: float, sector: str, config: dict) -> float:
    """Calculate WACC using CAPM for equity and sector debt cost."""
    rf   = config["LONG_TERM_RATE"]
    erp  = config["EQUITY_RISK_PREMIUM"]
    ke   = rf + beta * erp
    kd   = 0.055  # Typical Saudi corporate sukuk yield ~5.5%
    tax  = config["CORPORATE_TAX_RATE"]
    eq   = 1 - debt_ratio
    wacc = ke * eq + kd * (1 - tax) * debt_ratio
    return max(config["WACC_MIN"], min(config["WACC_MAX"], wacc))


# ── FCF DCF for non-banking ──────────────────────────────────────────────────

def _dcf_fcf(fcf: float, growth_stage1: float, growth_stage2: float,
             terminal_growth: float, wacc: float, n_years: int = 5) -> dict:
    """
    3-stage DCF:
      Stage 1: years 1-n_years at growth_stage1
      Stage 2: years n_years+1 to 10 fading to terminal_growth
      Terminal: Gordon Growth Model
    Returns dict with pv_stage1, pv_stage2, pv_terminal, total_value.
    """
    if wacc <= terminal_growth:
        terminal_growth = wacc * 0.60  # Safety clamp

    pv_s1 = 0.0
    cf = fcf
    for yr in range(1, n_years + 1):
        cf *= (1 + growth_stage1)
        pv_s1 += cf / ((1 + wacc) ** yr)

    # Stage 2 — linear fade
    pv_s2 = 0.0
    for yr in range(n_years + 1, 11):
        fade  = (yr - n_years) / (10 - n_years)
        g_yr  = growth_stage1 + fade * (terminal_growth - growth_stage1)
        cf   *= (1 + g_yr)
        pv_s2 += cf / ((1 + wacc) ** yr)

    # Terminal value
    cf_terminal  = cf * (1 + terminal_growth)
    tv           = cf_terminal / (wacc - terminal_growth)
    pv_terminal  = tv / ((1 + wacc) ** 10)
    total        = pv_s1 + pv_s2 + pv_terminal

    return {
        "pv_stage1":    round(pv_s1, 2),
        "pv_stage2":    round(pv_s2, 2),
        "pv_terminal":  round(pv_terminal, 2),
        "total_value":  round(total, 2),
        "terminal_pct": round(pv_terminal / total, 4) if total > 0 else 0,
    }


# ── DDM for banking sector ────────────────────────────────────────────────────

def _ddm(dividend_per_share: float, growth: float, wacc: float) -> dict:
    """P = D1 / (Ke - g) — single stage DDM for Saudi banks."""
    d1    = dividend_per_share * (1 + growth)
    spread = wacc - growth
    if spread <= 0:
        spread = 0.01
    price = d1 / spread
    return {
        "pv_stage1":    0,
        "pv_stage2":    0,
        "pv_terminal":  round(price, 2),
        "total_value":  round(price, 2),
        "terminal_pct": 1.0,
        "is_ddm":       True,
    }


# ── Per-ticker valuation ─────────────────────────────────────────────────────

def _value_ticker(ticker: str, info: dict, config: dict) -> Optional[dict]:
    """
    Compute bull/base/bear valuations for one ticker.
    Returns dict with scenarios or None if data insufficient.
    """
    sector  = KSA_SECTOR_MAP.get(ticker, "")
    is_bank = ticker in KSA_BANKING_TICKERS

    # Extract fundamentals
    price       = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    shares      = info.get("sharesOutstanding", 0)
    fcf         = info.get("freeCashflow", 0)
    beta        = info.get("beta") or 1.0
    total_debt  = info.get("totalDebt", 0)
    total_assets = info.get("totalAssets", 0) or 1
    mkt_cap     = info.get("marketCap", 0)
    dividend    = info.get("dividendRate") or info.get("trailingAnnualDividendRate", 0)
    net_income  = info.get("netIncomeToCommon", 0)
    net_debt    = total_debt - (info.get("totalCash") or 0)

    if not price or not shares:
        return None

    debt_ratio = min(total_debt / total_assets, 0.80)
    tg_base    = config["SECTOR_GROWTH_OVERRIDES"].get(sector, config["TERMINAL_GROWTH_RATE"])

    # Per-scenario growth rates
    scenarios = {
        "bull": {
            "growth_s1": tg_base + 0.04,
            "growth_s2": tg_base + 0.02,
            "terminal":  tg_base + 0.01,
            "wacc_adj":  -0.005,
            "weight":    config["BULL_WEIGHT"],
        },
        "base": {
            "growth_s1": tg_base,
            "growth_s2": tg_base * 0.85,
            "terminal":  tg_base,
            "wacc_adj":  0.0,
            "weight":    config["BASE_WEIGHT"],
        },
        "bear": {
            "growth_s1": tg_base - 0.03,
            "growth_s2": tg_base - 0.02,
            "terminal":  tg_base - 0.01,
            "wacc_adj":  +0.010,
            "weight":    config["BEAR_WEIGHT"],
        },
    }

    results = {}
    weighted_intrinsic = 0.0

    for scen_name, sp in scenarios.items():
        wacc = _calc_wacc(beta, debt_ratio, sector, config) + sp["wacc_adj"]
        wacc = max(config["WACC_MIN"], min(config["WACC_MAX"], wacc))

        if is_bank:
            dps = dividend or (net_income / shares * 0.50 if shares else 0)
            val = _ddm(dps, sp["terminal"], wacc)
        else:
            base_fcf = fcf if fcf and fcf > 0 else net_income * 0.60
            if not base_fcf:
                continue
            val = _dcf_fcf(
                fcf=base_fcf / shares if shares else base_fcf,
                growth_stage1=sp["growth_s1"],
                growth_stage2=sp["growth_s2"],
                terminal_growth=max(0.01, sp["terminal"]),
                wacc=wacc,
            )

        intrinsic = val["total_value"]
        # Adjust enterprise value for debt
        if not is_bank and net_debt and shares:
            intrinsic -= net_debt / shares

        intrinsic = max(0, intrinsic)
        mos       = (intrinsic - price) / price if price > 0 else 0
        label     = _valuation_label(mos, config)

        results[scen_name] = {
            "scenario":              scen_name,
            "intrinsic_per_share":   round(intrinsic, 2),
            "current_price":         round(price, 2),
            "margin_of_safety":      round(mos, 4),
            "upside_pct":            round(mos, 4),
            "valuation_label":       label,
            "dcf_confidence":        _confidence(val.get("terminal_pct", 0), intrinsic, price),
            "enterprise_value":      round(mkt_cap + total_debt, 2) if mkt_cap else None,
            "pv_stage1":             val.get("pv_stage1"),
            "pv_stage2":             val.get("pv_stage2"),
            "pv_terminal":           val.get("pv_terminal"),
            "terminal_value_pct":    val.get("terminal_pct"),
            "terminal_value_warning": val.get("terminal_pct", 0) > 0.80,
            "wacc":                  round(wacc, 4),
            "beta_used":             round(beta, 4),
            "terminal_growth":       round(sp["terminal"], 4),
            "net_debt":              round(net_debt, 2),
            "is_banking_ddm":        is_bank,
        }
        weighted_intrinsic += intrinsic * sp["weight"]

    if not results:
        return None

    # Composite weighted intrinsic
    mos_weighted = (weighted_intrinsic - price) / price if price > 0 else 0
    results["weighted"] = {
        "intrinsic_per_share": round(weighted_intrinsic, 2),
        "margin_of_safety":    round(mos_weighted, 4),
        "valuation_label":     _valuation_label(mos_weighted, config),
        "current_price":       round(price, 2),
    }

    return results


def _valuation_label(mos: float, config: dict) -> str:
    if mos >= config["DEEP_VALUE_MOS"]:       return "DEEP_VALUE"
    if mos >= config["UNDERVALUED_MOS"]:      return "UNDERVALUED"
    if abs(mos) <= config["FAIR_VALUE_BAND"]: return "FAIR_VALUE"
    if mos <= -config["SPECULATIVE_PREMIUM"]: return "SPECULATIVE"
    if mos < 0:                               return "OVERVALUED"
    return "FAIR_VALUE"


def _confidence(terminal_pct: float, intrinsic: float, price: float) -> str:
    if terminal_pct > 0.85:    return "LOW"     # Too terminal-value dependent
    if abs(intrinsic - price) / max(price, 1) < 0.05: return "LOW"
    if terminal_pct < 0.60:    return "HIGH"
    return "MEDIUM"


# ── DB persistence ────────────────────────────────────────────────────────────

def _ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ksa_dcf_valuations (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                market_id VARCHAR(10) DEFAULT 'KSA',
                scenario VARCHAR(10) NOT NULL,
                intrinsic_per_share NUMERIC(12,2),
                current_price NUMERIC(12,2),
                margin_of_safety NUMERIC(6,4),
                upside_pct NUMERIC(6,4),
                valuation_label VARCHAR(20),
                dcf_confidence VARCHAR(10),
                enterprise_value NUMERIC(18,2),
                pv_stage1 NUMERIC(18,2),
                pv_stage2 NUMERIC(18,2),
                pv_terminal NUMERIC(18,2),
                terminal_value_pct NUMERIC(6,4),
                terminal_value_warning BOOLEAN DEFAULT FALSE,
                wacc NUMERIC(6,4),
                beta_used NUMERIC(6,4),
                terminal_growth NUMERIC(6,4),
                net_debt NUMERIC(18,2),
                years_of_data INTEGER,
                is_banking_ddm BOOLEAN DEFAULT FALSE,
                raw_json TEXT,
                computed_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(ticker, market_id, scenario, DATE(computed_at))
            )
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.debug(f"[KSA DCF] Table ensure error: {e}")
    finally:
        cur.close()


def _upsert_valuation(conn, ticker: str, scen: str, val: dict):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ksa_dcf_valuations
                (ticker, market_id, scenario, intrinsic_per_share, current_price,
                 margin_of_safety, upside_pct, valuation_label, dcf_confidence,
                 enterprise_value, pv_stage1, pv_stage2, pv_terminal,
                 terminal_value_pct, terminal_value_warning,
                 wacc, beta_used, terminal_growth, net_debt, is_banking_ddm, raw_json)
            VALUES (%s,'KSA',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ticker, market_id, scenario, DATE(computed_at))
            DO UPDATE SET
                intrinsic_per_share  = EXCLUDED.intrinsic_per_share,
                margin_of_safety     = EXCLUDED.margin_of_safety,
                valuation_label      = EXCLUDED.valuation_label,
                dcf_confidence       = EXCLUDED.dcf_confidence,
                terminal_value_warning = EXCLUDED.terminal_value_warning,
                computed_at          = NOW()
        """, (
            ticker, scen,
            val.get("intrinsic_per_share"), val.get("current_price"),
            val.get("margin_of_safety"),    val.get("upside_pct"),
            val.get("valuation_label"),     val.get("dcf_confidence"),
            val.get("enterprise_value"),
            val.get("pv_stage1"),           val.get("pv_stage2"),
            val.get("pv_terminal"),         val.get("terminal_value_pct"),
            val.get("terminal_value_warning", False),
            val.get("wacc"),                val.get("beta_used"),
            val.get("terminal_growth"),     val.get("net_debt"),
            val.get("is_banking_ddm", False),
            json.dumps(val),
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.debug(f"[KSA DCF] Upsert error {ticker}/{scen}: {e}")
    finally:
        cur.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def run_ksa_dcf(tickers: list = None, force: bool = False):
    """
    Run DCF valuation for all KSA tickers (Sundays only unless force=True).
    """
    from datetime import datetime as _dt
    if not force and _dt.now().weekday() != 6:
        logger.info("[KSA DCF] Not Sunday -- skipping. Use force=True to override.")
        return

    import yfinance as yf
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    _ensure_table(conn)

    tickers = tickers or [t["symbol"] for t in KSA_TOP50[:20]]
    config  = KSA_DCF_CONFIG
    valued  = 0

    logger.info(f"[KSA DCF] Starting valuation for {len(tickers)} tickers")

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            if not info:
                logger.debug(f"[KSA DCF] No info for {ticker}")
                continue

            scen_results = _value_ticker(ticker, info, config)
            if not scen_results:
                logger.debug(f"[KSA DCF] Insufficient data for {ticker}")
                continue

            for scen_name, val in scen_results.items():
                _upsert_valuation(conn, ticker, scen_name, val)

            base = scen_results.get("base", {})
            label = base.get("valuation_label", "-")
            mos   = base.get("margin_of_safety", 0)
            logger.info(f"[KSA DCF] {ticker}: {label} MoS={mos:.1%}")
            valued += 1

        except Exception as e:
            logger.warning(f"[KSA DCF] Error for {ticker}: {e}")

    conn.close()
    logger.info(f"[KSA DCF] Complete -- {valued}/{len(tickers)} tickers valued")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",  action="store_true", help="Run even if not Sunday")
    parser.add_argument("--ticker", help="Single ticker")
    args = parser.parse_args()
    tickers = [args.ticker] if args.ticker else None
    run_ksa_dcf(tickers=tickers, force=args.force)
