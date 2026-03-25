"""
Portfolio circuit breaker based on latest drawdown.
"""

import logging
import os
from decimal import Decimal, ROUND_HALF_UP

from database import get_connection, sql_bool

logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")


def _ph(idx: int) -> str:
    return "%s" if DATABASE_URL else "?"


def apply_circuit_breaker(portfolio_type: str, config, allocation):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT pp.max_drawdown_pct
            FROM portfolio_performance pp
            JOIN model_portfolios mp ON pp.portfolio_id = mp.id
            WHERE mp.portfolio_type = {_ph(1)} AND mp.is_active = {sql_bool(True)}
            ORDER BY pp.snapshot_date DESC
            LIMIT 1
            """,
            (portfolio_type,),
        )
        row = cursor.fetchone()

    if not row:
        return allocation

    current_drawdown = abs(float(row[0] if not isinstance(row, dict) else row.get("max_drawdown_pct") or 0))
    if current_drawdown <= float(config.target_max_drawdown_pct):
        return allocation

    target_drawdown = float(config.target_max_drawdown_pct)
    excess_ratio = (current_drawdown - target_drawdown) / target_drawdown if target_drawdown > 0 else 1.0
    additional_cash = min(15.0, 10.0 + excess_ratio * 5.0)

    max_cash = Decimal(str(config.max_cash_pct))
    new_cash = min(max_cash, allocation.cash_pct + Decimal(str(additional_cash)))

    invested = Decimal("100") - allocation.cash_pct
    if invested > 0:
        factor = (Decimal("100") - new_cash) / invested
        for alloc in allocation.allocations:
            alloc["allocation"] = (alloc["allocation"] * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    allocation.cash_pct = new_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocation.metadata["circuit_breaker_triggered"] = True
    allocation.metadata["drawdown_pct"] = current_drawdown
    allocation.metadata["additional_cash"] = additional_cash

    logger.warning(
        "Circuit breaker triggered for %s: drawdown %.2f%% > %.2f%%",
        portfolio_type,
        current_drawdown,
        target_drawdown,
    )
    return allocation
