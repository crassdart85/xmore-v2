"""
Screening Engine — Strategic stock screening and portfolio construction.

Provides:
  compute_top_picks()       — daily batch: best 5 stocks by weighted score
  compute_sector_rotation() — daily batch: top sectors by buy-signal strength
  get_ranked_signals()      — real-time ranked BUY signals (confidence + win-rate)
  build_portfolio()         — allocate a budget across ranked signals with risk rules
"""

import logging
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from database import is_postgres, sql_bool

logger = logging.getLogger(__name__)

DATABASE_URL = is_postgres()

# Sector rotation scoring constants
# Volatility (daily std of returns) is typically ~0.01–0.05; multiplying by 100
# converts it to a "percent points" scale comparable to buy_signal_count values.
VOLATILITY_SCALE = 100
MAX_VOLATILITY_PENALTY = 5.0


def _ph(n: int) -> str:
    """Return the correct placeholder for the active DB backend."""
    return "%s" if DATABASE_URL else "?"


def _conviction_to_score(conviction: Optional[str]) -> float:
    """Map conviction text to a 0–100 numeric score."""
    mapping = {
        "STRONG": 90.0,
        "HIGH": 80.0,
        "MEDIUM": 60.0,
        "LOW": 40.0,
        "VERY_LOW": 20.0,
    }
    if conviction is None:
        return 50.0
    return mapping.get(str(conviction).upper(), 50.0)


def _signal_base_score(signal: str) -> float:
    """Translate final_signal to a base weight for top-picks ranking."""
    mapping = {
        "STRONG_BUY": 1.0,
        "BUY": 0.8,
        "UP": 0.7,
        "HOLD": 0.3,
        "DOWN": 0.1,
        "SELL": 0.1,
        "STRONG_SELL": 0.0,
    }
    return mapping.get(str(signal).upper(), 0.3)


def _get_sector(symbol: str, symbol_sector: Dict[str, str]) -> str:
    """Look up the sector for a symbol, trying both raw and stripped-suffix forms."""
    return (
        symbol_sector.get(symbol)
        or symbol_sector.get(symbol.replace(".CA", ""))
        or "Unknown"
    )


# ─────────────────────────────────────────────
# 1. COMPUTE TOP PICKS
# ─────────────────────────────────────────────

def compute_top_picks(conn, pick_date: Optional[str] = None, top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Compute and upsert the best `top_n` stocks for `pick_date`.

    Weighted score formula:
        0.4 * conviction_norm  +  0.3 * sentiment_norm  +  0.3 * signal_base

    Idempotent — safe to call multiple times per day.

    Args:
        conn:       Active DB connection (from database.get_connection()).
        pick_date:  ISO date string (defaults to today).
        top_n:      Number of picks to produce (default 5).

    Returns:
        List of pick dicts ordered by rank.
    """
    if pick_date is None:
        pick_date = date.today().isoformat()

    cursor = conn.cursor()

    # Fetch latest consensus results for the requested date
    cursor.execute(
        f"""
        SELECT cr.symbol, cr.final_signal, cr.conviction, cr.confidence,
               cr.bull_score, cr.bear_score,
               COALESCE(ss.avg_sentiment, 0) AS avg_sentiment,
               COALESCE(p.close, 0) AS entry_price
        FROM consensus_results cr
        LEFT JOIN sentiment_scores ss
               ON ss.symbol = cr.symbol
              AND ss.date = cr.prediction_date
        LEFT JOIN (
            SELECT symbol, close, date
            FROM prices
            WHERE (symbol, date) IN (
                SELECT symbol, MAX(date) FROM prices GROUP BY symbol
            )
        ) p ON p.symbol = cr.symbol
        WHERE cr.prediction_date = {_ph(1)}
          AND cr.final_signal NOT IN ('HOLD', 'DOWN', 'SELL', 'STRONG_SELL')
          AND cr.risk_action NOT IN ('BLOCK')
        ORDER BY cr.confidence DESC
        """,
        (pick_date,),
    )
    rows = cursor.fetchall()

    if not rows:
        return []

    picks = []
    for row in rows:
        row = dict(row)
        conviction_norm = _conviction_to_score(row.get("conviction")) / 100.0
        # Normalise avg_sentiment from [-1,1] to [0,1]
        sentiment_raw = float(row.get("avg_sentiment") or 0.0)
        sentiment_norm = (sentiment_raw + 1.0) / 2.0
        signal_base = _signal_base_score(row.get("final_signal") or "HOLD")

        weighted_score = (
            0.4 * conviction_norm
            + 0.3 * sentiment_norm
            + 0.3 * signal_base
        )

        # Simple target price estimate: entry × 1.05 (5% gain over 5 days proxy)
        entry_price = float(row.get("entry_price") or 0.0)
        target_price = round(entry_price * 1.05, 2) if entry_price > 0 else None

        rationale = (
            f"{row['final_signal']} signal with {row.get('conviction', 'LOW')} conviction. "
            f"Sentiment score: {sentiment_raw:+.2f}. "
            f"Composite weighted score: {weighted_score:.2f}."
        )

        picks.append(
            {
                "symbol": row["symbol"],
                "consensus_signal": row["final_signal"],
                "conviction": row.get("conviction"),
                "sentiment_score": round(sentiment_raw, 4),
                "weighted_score": round(weighted_score, 4),
                "entry_price": entry_price if entry_price > 0 else None,
                "target_price": target_price,
                "rationale": rationale,
            }
        )

    # Sort and take top N
    picks.sort(key=lambda x: x["weighted_score"], reverse=True)
    top_picks = picks[:top_n]

    # Upsert into daily_top_picks
    for rank, pick in enumerate(top_picks, start=1):
        if DATABASE_URL:
            cursor.execute(
                """
                INSERT INTO daily_top_picks
                    (pick_date, rank, symbol, consensus_signal, conviction,
                     sentiment_score, weighted_score, entry_price, target_price, rationale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pick_date, rank)
                DO UPDATE SET
                    symbol           = EXCLUDED.symbol,
                    consensus_signal = EXCLUDED.consensus_signal,
                    conviction       = EXCLUDED.conviction,
                    sentiment_score  = EXCLUDED.sentiment_score,
                    weighted_score   = EXCLUDED.weighted_score,
                    entry_price      = EXCLUDED.entry_price,
                    target_price     = EXCLUDED.target_price,
                    rationale        = EXCLUDED.rationale
                """,
                (
                    pick_date, rank, pick["symbol"], pick["consensus_signal"],
                    pick["conviction"], pick["sentiment_score"], pick["weighted_score"],
                    pick["entry_price"], pick["target_price"], pick["rationale"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT OR REPLACE INTO daily_top_picks
                    (pick_date, rank, symbol, consensus_signal, conviction,
                     sentiment_score, weighted_score, entry_price, target_price, rationale)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pick_date, rank, pick["symbol"], pick["consensus_signal"],
                    pick["conviction"], pick["sentiment_score"], pick["weighted_score"],
                    pick["entry_price"], pick["target_price"], pick["rationale"],
                ),
            )
        pick["rank"] = rank
        pick["pick_date"] = pick_date

    return top_picks


# ─────────────────────────────────────────────
# 2. COMPUTE SECTOR ROTATION
# ─────────────────────────────────────────────

def compute_sector_rotation(conn, rotation_date: Optional[str] = None, top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Aggregate consensus signals by sector and rank them.

    Composite score = buy_signal_count  +  avg_conviction_score/100  -  volatility_penalty

    Args:
        conn:          Active DB connection.
        rotation_date: ISO date string (defaults to today).
        top_n:         Number of top sectors to return (default 3).

    Returns:
        List of sector dicts ordered by rank.
    """
    from egx_symbols import EGX_SYMBOL_DATABASE  # avoid circular at module level

    if rotation_date is None:
        rotation_date = date.today().isoformat()

    # Build symbol → sector mapping from the local EGX symbol DB
    symbol_sector: Dict[str, str] = {}
    for stock in EGX_SYMBOL_DATABASE.values():
        symbol_sector[stock.yahoo] = stock.sector
        symbol_sector[stock.ticker] = stock.sector

    cursor = conn.cursor()
    # Fetch consensus results for the requested date
    cursor.execute(
        f"""
        SELECT cr.symbol, cr.final_signal, cr.conviction, cr.confidence
        FROM consensus_results cr
        WHERE cr.prediction_date = {_ph(1)}
        """,
        (rotation_date,),
    )
    rows = cursor.fetchall()

    # Fetch 20-day volatility per symbol from the prices table
    cursor.execute("SELECT symbol, close FROM prices ORDER BY symbol, date DESC")
    price_rows = cursor.fetchall()

    # Build per-symbol close history for vol calculation
    from collections import defaultdict
    close_hist: Dict[str, List[float]] = defaultdict(list)
    for pr in price_rows:
        pr = dict(pr)
        close_hist[pr["symbol"]].append(float(pr["close"] or 0))

    def _symbol_vol(sym: str) -> float:
        closes = close_hist.get(sym, [])
        if len(closes) < 2:
            return 0.0
        tail = closes[:20]  # already DESC-ordered — first 20 are most recent
        import statistics
        try:
            changes = [(tail[i] - tail[i + 1]) / tail[i + 1]
                       for i in range(len(tail) - 1) if tail[i + 1] > 0]
            return statistics.stdev(changes) if len(changes) >= 2 else 0.0
        except Exception:
            return 0.0

    # Aggregate per sector
    sector_data: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        row = dict(row)
        sym = row.get("symbol", "")
        sector = _get_sector(sym, symbol_sector)
        signal = str(row.get("final_signal") or "HOLD").upper()
        conviction_score = _conviction_to_score(row.get("conviction"))
        volatility = _symbol_vol(sym)

        if sector not in sector_data:
            sector_data[sector] = {
                "sector": sector,
                "buy_signal_count": 0,
                "conviction_sum": 0.0,
                "conviction_count": 0,
                "volatility_sum": 0.0,
                "volatility_count": 0,
            }

        if signal in ("BUY", "STRONG_BUY", "UP"):
            sector_data[sector]["buy_signal_count"] += 1

        sector_data[sector]["conviction_sum"] += conviction_score
        sector_data[sector]["conviction_count"] += 1

        if volatility > 0:
            sector_data[sector]["volatility_sum"] += volatility
            sector_data[sector]["volatility_count"] += 1

    if not sector_data:
        return []

    # Compute composite score
    results = []
    for sector, data in sector_data.items():
        avg_conviction = (
            data["conviction_sum"] / data["conviction_count"]
            if data["conviction_count"] > 0
            else 50.0
        )
        avg_volatility = (
            data["volatility_sum"] / data["volatility_count"]
            if data["volatility_count"] > 0
            else 0.0
        )
        # Penalise volatile sectors — scale daily-return std to "percent points" space,
        # then cap at MAX_VOLATILITY_PENALTY to prevent extreme values dominating the score.
        volatility_penalty = min(avg_volatility * VOLATILITY_SCALE, MAX_VOLATILITY_PENALTY)

        composite = (
            data["buy_signal_count"]
            + avg_conviction / 100.0
            - volatility_penalty
        )

        results.append(
            {
                "sector": sector,
                "buy_signal_count": data["buy_signal_count"],
                "avg_conviction": round(avg_conviction, 2),
                "volatility_20d": round(avg_volatility, 6),
                "composite_score": round(composite, 4),
                "recommended_allocation": None,  # set after ranking
            }
        )

    # Rank sectors
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    top_sectors = results[:top_n]

    # Assign equal recommended allocation across top sectors
    alloc_each = round(100.0 / top_n, 1)
    for rank, sector in enumerate(top_sectors, start=1):
        sector["rank"] = rank
        sector["rotation_date"] = rotation_date
        sector["recommended_allocation"] = alloc_each

        if DATABASE_URL:
            cursor.execute(
                """
                INSERT INTO daily_sector_rotation
                    (rotation_date, sector, buy_signal_count, avg_conviction,
                     volatility_20d, composite_score, rank, recommended_allocation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rotation_date, sector)
                DO UPDATE SET
                    buy_signal_count      = EXCLUDED.buy_signal_count,
                    avg_conviction        = EXCLUDED.avg_conviction,
                    volatility_20d        = EXCLUDED.volatility_20d,
                    composite_score       = EXCLUDED.composite_score,
                    rank                  = EXCLUDED.rank,
                    recommended_allocation = EXCLUDED.recommended_allocation
                """,
                (
                    rotation_date, sector["sector"], sector["buy_signal_count"],
                    sector["avg_conviction"], sector["volatility_20d"],
                    sector["composite_score"], rank, alloc_each,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT OR REPLACE INTO daily_sector_rotation
                    (rotation_date, sector, buy_signal_count, avg_conviction,
                     volatility_20d, composite_score, rank, recommended_allocation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rotation_date, sector["sector"], sector["buy_signal_count"],
                    sector["avg_conviction"], sector["volatility_20d"],
                    sector["composite_score"], rank, alloc_each,
                ),
            )

    return top_sectors


# ─────────────────────────────────────────────
# 3. GET RANKED SIGNALS
# ─────────────────────────────────────────────

def get_ranked_signals(conn, signal_date: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Return active BUY signals sorted by:
      1. Confidence (highest first)
      2. Recent win rate (last 20 predictions per stock)
      3. Days since signal (fresher signals rank higher within the same confidence band)

    Args:
        conn:        Active DB connection.
        signal_date: ISO date string (defaults to today).
        limit:       Maximum rows to return.

    Returns:
        List of signal dicts.
    """
    if signal_date is None:
        signal_date = date.today().isoformat()

    cursor = conn.cursor()

    # Win rate from last 20 evaluated predictions per symbol
    win_rate_subquery = """
        SELECT symbol,
               CAST(SUM(CASE WHEN was_correct = {true_value} THEN 1 ELSE 0 END) AS REAL)
                   / NULLIF(COUNT(*), 0) AS recent_win_rate
        FROM (
            SELECT symbol, was_correct,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY evaluated_at DESC) AS rn
            FROM evaluations
            WHERE was_correct IS NOT NULL
        ) ranked
        WHERE rn <= 20
        GROUP BY symbol
    """.format(true_value=sql_bool(True))

    # Days since signal calculation
    days_old_expr = (
        "DATE_PART('day', CURRENT_DATE - cr.prediction_date::DATE)"
        if DATABASE_URL
        else "JULIANDAY('now') - JULIANDAY(cr.prediction_date)"
    )

    cursor.execute(
        f"""
        SELECT cr.symbol,
               cr.final_signal,
               cr.confidence,
               cr.conviction,
               cr.prediction_date,
               COALESCE(wr.recent_win_rate, 0.5) AS recent_win_rate,
               {days_old_expr} AS days_old,
               COALESCE(p.close, 0) AS entry_price,
               COALESCE(p.close * 1.05, 0) AS target_price
        FROM consensus_results cr
        LEFT JOIN ({win_rate_subquery}) wr ON wr.symbol = cr.symbol
        LEFT JOIN (
            SELECT symbol, close
            FROM prices
            WHERE (symbol, date) IN (
                SELECT symbol, MAX(date) FROM prices GROUP BY symbol
            )
        ) p ON p.symbol = cr.symbol
        WHERE cr.prediction_date = {_ph(1)}
          AND cr.final_signal IN ('BUY', 'STRONG_BUY', 'UP')
          AND cr.risk_action NOT IN ('BLOCK')
        ORDER BY cr.confidence DESC,
                 COALESCE(wr.recent_win_rate, 0.5) DESC,
                 {days_old_expr} ASC
        LIMIT {_ph(2)}
        """,
        (signal_date, limit),
    )
    rows = cursor.fetchall()

    return [
        {
            "symbol": dict(r)["symbol"],
            "signal": dict(r)["final_signal"],
            "confidence": float(dict(r)["confidence"] or 0),
            "conviction": dict(r)["conviction"],
            "recent_win_rate": round(float(dict(r)["recent_win_rate"] or 0.5), 4),
            "days_old": int(float(dict(r)["days_old"] or 0)),
            "entry_price": float(dict(r)["entry_price"] or 0) or None,
            "target_price": round(float(dict(r)["target_price"] or 0), 2) or None,
            "signal_date": dict(r)["prediction_date"],
        }
        for r in rows
    ]


# ─────────────────────────────────────────────
# 4. BUILD PORTFOLIO
# ─────────────────────────────────────────────

def build_portfolio(
    conn,
    budget_egp: float,
    risk_tolerance_pct: float = 5.0,
    signal_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Allocate `budget_egp` across ranked BUY signals applying risk constraints.

    Rules:
    - Max 15% per position
    - Max 3 positions from the same sector
    - Equal-weight top 5–7 signals
    - Stop-loss: 6% below entry price
    - Target: 5% above entry price (T+5 proxy)
    - Validation: sum(entry_egp) <= budget, sum(risk_egp) <= risk_tolerance_pct% of budget

    Args:
        conn:               Active DB connection.
        budget_egp:         Total portfolio budget in EGP.
        risk_tolerance_pct: Max percentage of budget to risk (default 5%).
        signal_date:        ISO date string (defaults to today).

    Returns:
        Dict with positions list and portfolio summary.
    """
    from egx_symbols import EGX_SYMBOL_DATABASE  # avoid circular

    if signal_date is None:
        signal_date = date.today().isoformat()

    max_risk_egp = budget_egp * risk_tolerance_pct / 100.0
    max_position_pct = 0.15
    max_per_sector = 3

    # Build sector map
    symbol_sector: Dict[str, str] = {}
    for stock in EGX_SYMBOL_DATABASE.values():
        symbol_sector[stock.yahoo] = stock.sector
        symbol_sector[stock.ticker] = stock.sector

    # Fetch ranked BUY signals
    candidates = get_ranked_signals(conn, signal_date=signal_date, limit=50)

    # Filter to signals with valid entry prices
    candidates = [c for c in candidates if c.get("entry_price") and c["entry_price"] > 0]

    if not candidates:
        return {
            "status": "no_signals",
            "budget_egp": budget_egp,
            "positions": [],
            "summary": {"total_invested": 0, "total_risk": 0, "position_count": 0},
        }

    # Apply sector concentration constraint
    sector_counts: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []

    for candidate in candidates:
        sym = candidate["symbol"]
        sector = _get_sector(sym, symbol_sector)

        if sector_counts.get(sector, 0) >= max_per_sector:
            continue

        selected.append({**candidate, "sector": sector})
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

        if len(selected) >= 7:
            break

    if not selected:
        return {
            "status": "no_eligible_signals",
            "budget_egp": budget_egp,
            "positions": [],
            "summary": {"total_invested": 0, "total_risk": 0, "position_count": 0},
        }

    # Equal-weight allocation (cap at max_position_pct)
    n = len(selected)
    raw_weight = 1.0 / n
    position_weight = min(raw_weight, max_position_pct)
    alloc_per_position = budget_egp * position_weight

    positions = []
    total_invested = 0.0
    total_risk = 0.0

    for sig in selected:
        entry = float(sig["entry_price"])
        stop_loss = round(entry * 0.94, 2)
        target = round(entry * 1.05, 2)
        risk_per_share = entry - stop_loss

        qty = max(1, int(alloc_per_position / entry))
        entry_egp = round(qty * entry, 2)
        risk_egp = round(qty * risk_per_share, 2)

        # Clamp to budget
        if total_invested + entry_egp > budget_egp:
            remaining = budget_egp - total_invested
            if remaining < entry:
                break
            qty = max(1, int(remaining / entry))
            entry_egp = round(qty * entry, 2)
            risk_egp = round(qty * risk_per_share, 2)

        positions.append(
            {
                "symbol": sig["symbol"],
                "sector": sig["sector"],
                "signal": sig["signal"],
                "confidence": sig["confidence"],
                "recent_win_rate": sig["recent_win_rate"],
                "qty": qty,
                "entry_price": entry,
                "entry_egp": entry_egp,
                "stop_loss": stop_loss,
                "target": target,
                "risk_egp": risk_egp,
            }
        )
        total_invested += entry_egp
        total_risk += risk_egp

    # Validation flags
    budget_ok = total_invested <= budget_egp + 1.0  # tiny float tolerance
    risk_ok = total_risk <= max_risk_egp + 1.0

    return {
        "status": "ok",
        "budget_egp": budget_egp,
        "risk_tolerance_pct": risk_tolerance_pct,
        "signal_date": signal_date,
        "positions": positions,
        "summary": {
            "position_count": len(positions),
            "total_invested": round(total_invested, 2),
            "cash_remaining": round(budget_egp - total_invested, 2),
            "total_risk_egp": round(total_risk, 2),
            "budget_constraint_met": budget_ok,
            "risk_constraint_met": risk_ok,
        },
    }
