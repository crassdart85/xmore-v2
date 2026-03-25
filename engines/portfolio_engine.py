"""
Portfolio Engine - Signal-to-Allocation Pipeline.
Uses database.get_connection for SQLite/PostgreSQL compatibility.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List

from database import get_connection, is_postgres, sql_bool, sql_today
from engines.portfolio_config import (
    AGGRESSIVE_CONFIG,
    BALANCED_CONFIG,
    CONSERVATIVE_CONFIG,
    PortfolioConfig,
)

logger = logging.getLogger(__name__)
DATABASE_URL = is_postgres()


def _ph(idx: int) -> str:
    return "%s" if DATABASE_URL else "?"


def _json_to_dict(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


@dataclass
class Signal:
    stock_symbol: str
    stock_name_ar: str
    action: str
    consensus_score: float
    agent_votes: Dict
    confidence_level: str
    entry_price: Decimal
    stop_loss_price: Decimal
    target_price: Decimal
    sector: str
    is_egx30: bool = False


@dataclass
class ScoredSignal:
    signal: Signal
    score: float


@dataclass
class PortfolioAllocation:
    allocations: List[Dict]
    cash_pct: Decimal
    metadata: Dict


def collect_active_signals() -> List[Signal]:
    signals: List[Signal] = []
    seen_symbols = set()
    action_values = ("BUY", "STRONG_BUY", "WATCH")

    sql = f"""
        SELECT
            tr.symbol AS stock_symbol,
            COALESCE(s.name_ar, tr.symbol) AS stock_name_ar,
            tr.action,
            COALESCE(tr.consensus_score, 0) AS consensus_score,
            COALESCE(tr.agent_votes, '{{}}') AS agent_votes,
            COALESCE(tr.conviction, 'LOW') AS confidence_level,
            COALESCE(tr.close_price, 0) AS entry_price,
            COALESCE(tr.stop_loss_price, 0) AS stop_loss_price,
            COALESCE(tr.target_price, 0) AS target_price,
            COALESCE(s.sector_en, 'Unknown') AS sector,
            CASE WHEN s.id IS NULL THEN {sql_bool(False)} ELSE {sql_bool(True)} END AS is_egx30
        FROM trade_recommendations tr
        LEFT JOIN egx30_stocks s ON tr.symbol = s.symbol
        WHERE tr.action IN ({_ph(1)}, {_ph(2)}, {_ph(3)})
          AND tr.recommendation_date = {sql_today()}
        ORDER BY (tr.priority IS NULL), tr.priority DESC, (tr.confidence IS NULL), tr.confidence DESC
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, action_values)
        rows = cursor.fetchall()

        for row in rows:
            if isinstance(row, dict):
                r = row
            else:
                cols = [c[0] for c in cursor.description]
                r = dict(zip(cols, row))
            symbol = r["stock_symbol"]
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            signals.append(
                Signal(
                    stock_symbol=symbol,
                    stock_name_ar=r.get("stock_name_ar") or symbol,
                    action=str(r["action"]).lower(),
                    consensus_score=float(r.get("consensus_score") or 0),
                    agent_votes=_json_to_dict(r.get("agent_votes")),
                    confidence_level=str(r.get("confidence_level") or "LOW"),
                    entry_price=Decimal(str(r.get("entry_price") or 0)),
                    stop_loss_price=Decimal(str(r.get("stop_loss_price") or 0)),
                    target_price=Decimal(str(r.get("target_price") or 0)),
                    sector=r.get("sector") or "Unknown",
                    is_egx30=bool(r.get("is_egx30")),
                )
            )

    logger.info("Collected %s active signals", len(signals))
    return signals


def filter_signals_for_portfolio(signals: List[Signal], config: PortfolioConfig) -> List[Signal]:
    filtered = []
    for signal in signals:
        if signal.action not in config.allowed_signals:
            continue
        if signal.consensus_score < config.min_consensus_score:
            continue

        buy_votes = sum(1 for v in signal.agent_votes.values() if str(v).lower() in {"buy", "strong_buy"})
        total_votes = len(signal.agent_votes)
        if total_votes > 0 and buy_votes < config.min_agents_agree:
            continue

        if config.stock_universe == "egx30" and not signal.is_egx30:
            continue

        filtered.append(signal)

    logger.info("Filtered %s signals to %s for %s", len(signals), len(filtered), config.portfolio_type)
    return filtered


def score_and_rank(signals: List[Signal]) -> List[ScoredSignal]:
    scored: List[ScoredSignal] = []
    sector_counts: Dict[str, int] = {}

    for signal in signals:
        consensus = signal.consensus_score
        buy_votes = sum(1 for v in signal.agent_votes.values() if str(v).lower() in {"buy", "strong_buy"})
        total_votes = len(signal.agent_votes)
        agreement_ratio = buy_votes / total_votes if total_votes > 0 else 0.0

        upside = signal.target_price - signal.entry_price
        risk = signal.entry_price - signal.stop_loss_price
        risk_adjusted = 0.0
        if risk > 0:
            risk_adjusted = float(min(upside / risk, Decimal("3")))
            risk_adjusted /= 3.0

        sector_count = sector_counts.get(signal.sector, 0)
        sector_bonus = 1.0 if sector_count == 0 else max(0.0, 1.0 - sector_count * 0.25)
        sector_counts[signal.sector] = sector_count + 1

        momentum = consensus * 0.8
        score = (
            (consensus * 0.35)
            + (agreement_ratio * 0.25)
            + (risk_adjusted * 0.20)
            + (sector_bonus * 0.10)
            + (momentum * 0.10)
        )
        scored.append(ScoredSignal(signal=signal, score=score))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


def allocate_weights(scored_signals: List[ScoredSignal], config: PortfolioConfig) -> PortfolioAllocation:
    if not scored_signals:
        return PortfolioAllocation([], Decimal("100.00"), {"error": "No signals available"})

    max_stocks = config.max_stocks[1]
    selected_signals = scored_signals[:max_stocks]
    total_score = sum(s.score for s in selected_signals)
    available_for_stocks = Decimal("100") - Decimal(str(config.min_cash_pct))

    allocations: List[Dict] = []
    for sig in selected_signals:
        if total_score <= 0:
            raw_weight = Decimal("1") / Decimal(str(len(selected_signals)))
        else:
            raw_weight = Decimal(str(sig.score / total_score))
        allocation = (raw_weight * available_for_stocks).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        allocations.append(
            {
                "symbol": sig.signal.stock_symbol,
                "stock_name_ar": sig.signal.stock_name_ar,
                "allocation": allocation,
                "signal": sig.signal,
                "score": sig.score,
            }
        )

    max_pct = Decimal(str(config.max_single_stock_pct))
    for alloc in allocations:
        if alloc["allocation"] > max_pct:
            alloc["allocation"] = max_pct

    # Sector cap: trim lowest-scoring names in over-cap sectors.
    sector_totals: Dict[str, Decimal] = {}
    for alloc in allocations:
        sector = alloc["signal"].sector
        sector_totals[sector] = sector_totals.get(sector, Decimal("0")) + alloc["allocation"]
    for sector, total in sector_totals.items():
        max_sector = Decimal(str(config.max_sector_pct))
        if total <= max_sector:
            continue
        excess = total - max_sector
        sector_allocs = sorted([a for a in allocations if a["signal"].sector == sector], key=lambda x: x["score"])
        for item in sector_allocs:
            if excess <= 0:
                break
            reducible = min(item["allocation"], excess)
            item["allocation"] -= reducible
            excess -= reducible

    total_allocated = sum(a["allocation"] for a in allocations)
    cash_pct = Decimal("100") - total_allocated
    min_cash = Decimal(str(config.min_cash_pct))
    if total_allocated > 0 and cash_pct < min_cash:
        factor = (Decimal("100") - min_cash) / total_allocated
        for alloc in allocations:
            alloc["allocation"] = (alloc["allocation"] * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_allocated = sum(a["allocation"] for a in allocations)
        cash_pct = Decimal("100") - total_allocated

    cash_pct = cash_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    metadata = {
        "iteration_count": 1,
        "signals_considered": len(scored_signals),
        "signals_selected": len(allocations),
        "constraint_checks": ["single_stock_cap", "sector_cap", "cash_bounds"],
    }
    return PortfolioAllocation(allocations, cash_pct, metadata)


def validate_and_publish(portfolio_type: str, allocation: PortfolioAllocation, config: PortfolioConfig) -> int:
    if not allocation.allocations:
        logger.error("Validation failed: No allocations")
        return -1

    total_alloc = sum(a["allocation"] for a in allocation.allocations)
    total_with_cash = total_alloc + allocation.cash_pct
    if abs(float(total_with_cash) - 100.0) > 0.05:
        logger.error("Validation failed: total with cash=%s", total_with_cash)
        return -1

    for alloc in allocation.allocations:
        if float(alloc["allocation"]) > float(config.max_single_stock_pct):
            logger.error("Validation failed: %s above single-stock cap", alloc["symbol"])
            return -1

    days = 30 if config.rebalance_frequency == "monthly" else 14 if config.rebalance_frequency == "biweekly" else 7
    valid_until = datetime.now() + timedelta(days=days)

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                INSERT INTO model_portfolios
                (portfolio_type, total_stocks, cash_pct, is_active, valid_until, generation_metadata)
                VALUES ({_ph(1)}, {_ph(2)}, {_ph(3)}, {sql_bool(True)}, {_ph(4)}, {_ph(5)})
                """,
                (
                    portfolio_type,
                    len(allocation.allocations),
                    float(allocation.cash_pct),
                    valid_until,
                    json.dumps(allocation.metadata),
                ),
            )
            portfolio_id = cursor.fetchone()[0] if DATABASE_URL else cursor.lastrowid

            for alloc in allocation.allocations:
                signal = alloc["signal"]
                cursor.execute(
                    f"""
                    INSERT INTO portfolio_allocations
                    (portfolio_id, stock_symbol, stock_name_ar, allocation_pct, signal_type,
                     consensus_score, entry_price, stop_loss_price, target_price, rationale)
                    VALUES ({_ph(1)}, {_ph(2)}, {_ph(3)}, {_ph(4)}, {_ph(5)}, {_ph(6)}, {_ph(7)}, {_ph(8)}, {_ph(9)}, {_ph(10)})
                    """,
                    (
                        portfolio_id,
                        signal.stock_symbol,
                        alloc["stock_name_ar"],
                        float(alloc["allocation"]),
                        signal.action,
                        signal.consensus_score,
                        float(signal.entry_price),
                        float(signal.stop_loss_price),
                        float(signal.target_price),
                        json.dumps({"score": alloc["score"]}),
                    ),
                )
            return int(portfolio_id)
        except Exception:
            logger.exception("Failed to publish portfolio")
            return -1


CONFIGS = {
    "conservative": CONSERVATIVE_CONFIG,
    "balanced": BALANCED_CONFIG,
    "aggressive": AGGRESSIVE_CONFIG,
}
