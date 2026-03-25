"""
Professional Trading Metrics Calculator

All metrics are computed from existing tables:
- trade_recommendations (for signal-level accuracy)
- user_positions (for trade-level P&L)

Supports:
- Global, per-agent, per-stock, per-sector slicing
- Rolling 30/60/90-day windows
- Live-only filtering (excludes backtest data)
"""

import math
import os
from datetime import datetime, timezone
from database import get_connection, is_postgres, sql_bool, sql_days_ago

DATABASE_URL = is_postgres()

# EGX reporting basis should not inherit cross-market compatibility aliases.
EGX_RISK_FREE_RATE_ANNUAL = 0.2725
EGX_TRADING_DAYS_PER_YEAR = 247

try:
    from config.execution_config import EGX_ROUND_TRIP_RATE
except ImportError:
    EGX_ROUND_TRIP_RATE = 0.00725  # 0.725% round-trip baseline

# Daily risk-free rate: (1 + annual) ^ (1/247) - 1
EGX_DAILY_RF = (1 + EGX_RISK_FREE_RATE_ANNUAL) ** (1 / EGX_TRADING_DAYS_PER_YEAR) - 1
MINIMUM_TRADES_FOR_METRICS = 30


# ─── COST UTILITIES ──────────────────────────────────────────

def apply_transaction_costs(returns: list, cost_percents: list = None) -> list:
    """
    Deduct round-trip transaction costs from a gross return series.
    Returns are in percentage points (e.g. 2.5 = 2.5%).
    If cost_percents is provided it must have the same length as returns.
    Falls back to EGX_ROUND_TRIP_RATE * 100 (= 0.725 pp) per trade.
    """
    if not returns:
        return []
    default_cost_pct = EGX_ROUND_TRIP_RATE * 100  # 0.725 percentage points
    if cost_percents and len(cost_percents) == len(returns):
        return [r - c for r, c in zip(returns, cost_percents)]
    return [r - default_cost_pct for r in returns]


# ─── SQL HELPERS ───────────────────────────────────────────────

def _ph(index):
    """Return placeholder for parameterized query."""
    return '%s' if DATABASE_URL else '?'


def _query(cursor, sql, params=None):
    """Execute query and return list of dicts."""
    cursor.execute(sql, params or [])
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    result = []
    for row in rows:
        if isinstance(row, dict):
            result.append(row)
        else:
            result.append(dict(zip(columns, row)))
    return result


# ─── CORE METRICS QUERY ───────────────────────────────────────

def get_performance_summary(
    user_id: int = None,
    days: int = 90,
    live_only: bool = True,
    action_filter: str = None,
    symbol_filter: str = None,
    sector_filter: str = None
) -> dict:
    """
    Comprehensive performance summary.
    Returns all professional metrics in one call.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        conditions = ["tr.was_correct IS NOT NULL"]
        params = []

        if user_id:
            conditions.append(f"tr.user_id = {_ph(1)}")
            params.append(user_id)

        if live_only:
            conditions.append(f"(tr.is_live = {sql_bool(True)} OR tr.is_live IS NULL)")
            conditions.append(f"(tr.is_simulated = {sql_bool(False)} OR tr.is_simulated IS NULL)")

        if days:
            conditions.append(sql_days_ago("tr.recommendation_date", placeholder=_ph(len(params) + 1)))
            params.append(days)

        if action_filter:
            conditions.append(f"tr.action = {_ph(len(params)+1)}")
            params.append(action_filter.upper())

        if symbol_filter:
            conditions.append(f"tr.symbol = {_ph(len(params)+1)}")
            params.append(symbol_filter.upper())

        where = " AND ".join(conditions)

        sql = f"""
            SELECT
                tr.action, tr.signal, tr.confidence, tr.conviction,
                tr.actual_next_day_return AS return_1d,
                tr.actual_5day_return AS return_5d,
                tr.benchmark_1d_return AS bench_1d,
                tr.benchmark_5d_return AS bench_5d,
                tr.alpha_1d, tr.alpha_5d,
                tr.was_correct,
                tr.recommendation_date,
                tr.symbol,
                tr.round_trip_cost_egp,
                tr.position_value_egp
            FROM trade_recommendations tr
            WHERE {where}
            ORDER BY tr.recommendation_date ASC
        """

        try:
            rows = _query(cursor, sql, params)
        except Exception:
            return empty_metrics()

        if not rows:
            return empty_metrics()

        # Extract return series
        returns_1d = [float(r["return_1d"]) for r in rows if r.get("return_1d") is not None]
        returns_5d = [float(r["return_5d"]) for r in rows if r.get("return_5d") is not None]
        bench_1d = [float(r["bench_1d"]) for r in rows if r.get("bench_1d") is not None]
        alphas_1d = [float(r["alpha_1d"]) for r in rows if r.get("alpha_1d") is not None]
        correct = [r["was_correct"] for r in rows if r.get("was_correct") is not None]

        # Per-trade cost in percentage points (for cost-adjusted / net metrics)
        costs_pct = []
        for r in rows:
            if r.get("return_1d") is None:
                continue
            rtc = r.get("round_trip_cost_egp")
            pve = r.get("position_value_egp")
            if rtc and pve and float(pve) > 0:
                costs_pct.append(float(rtc) / float(pve) * 100)
            else:
                costs_pct.append(EGX_ROUND_TRIP_RATE * 100)  # default 0.725 pp

        returns_1d_net = apply_transaction_costs(returns_1d, costs_pct)
        cost_drag_total = sum(costs_pct) if costs_pct else 0.0
        profitable_after_cost = sum(1 for r in returns_1d_net if r > 0)
        profitability_accuracy = (
            round(profitable_after_cost / len(returns_1d_net) * 100, 1)
            if returns_1d_net else 0
        )

        return {
            # Core counts
            "total_predictions": len(rows),
            "resolved": len(correct),
            "period_days": days,
            "live_only": live_only,

            # Win/Loss
            "wins": sum(1 for c in correct if c),
            "losses": sum(1 for c in correct if not c),
            "win_rate": round(sum(1 for c in correct if c) / len(correct) * 100, 1) if correct else 0,

            # Returns
            "avg_return_1d": round(avg(returns_1d), 3),
            "avg_return_5d": round(avg(returns_5d), 3),
            "cumulative_return": round(cumulative_return(returns_1d), 2),
            "best_trade": round(max(returns_1d), 2) if returns_1d else 0,
            "worst_trade": round(min(returns_1d), 2) if returns_1d else 0,

            # Benchmark Comparison
            "avg_benchmark_1d": round(avg(bench_1d), 3),
            "avg_alpha_1d": round(avg(alphas_1d), 3),
            "cumulative_alpha": round(sum(alphas_1d), 2) if alphas_1d else 0,
            "beat_benchmark_pct": round(
                sum(1 for a in alphas_1d if a > 0) / len(alphas_1d) * 100, 1
            ) if alphas_1d else 0,

            # Risk Metrics (gross)
            "sharpe_ratio": round(sharpe_ratio(returns_1d), 2),
            "sortino_ratio": round(sortino_ratio(returns_1d), 2),
            "max_drawdown": round(max_drawdown(returns_1d), 2),
            "volatility": round(stddev(returns_1d), 3),
            "profit_factor": round(profit_factor(returns_1d), 2),

            # Net (cost-adjusted) metrics — use these for reporting
            "avg_return_1d_net": round(avg(returns_1d_net), 3),
            "cumulative_return_net": round(cumulative_return(returns_1d_net), 2),
            "sharpe_ratio_net": round(sharpe_ratio(returns_1d_net), 2),
            "sortino_ratio_net": round(sortino_ratio(returns_1d_net), 2),
            "max_drawdown_net": round(max_drawdown(returns_1d_net), 2),
            "profit_factor_net": round(profit_factor(returns_1d_net), 2),

            # P5: Directional accuracy vs profitability accuracy
            "profitability_accuracy": profitability_accuracy,  # % trades profitable after costs
            "cost_drag_total_pct": round(cost_drag_total, 2),
            "avg_cost_per_trade_pct": round(avg(costs_pct), 4) if costs_pct else 0,

            # Metadata
            "first_prediction": str(rows[0]["recommendation_date"]),
            "last_prediction": str(rows[-1]["recommendation_date"]),
            "live_trade_count": len(rows),
            "meets_minimum": len(rows) >= 100,
        }


# ─── METRIC CALCULATIONS ──────────────────────────────────────

def sharpe_ratio(returns: list, risk_free_rate: float = None, annualize: bool = True) -> float:
    """
    Sharpe Ratio = (avg_return - daily_rf) / stdev(returns)
    Annualized using EGX_TRADING_DAYS_PER_YEAR (247, Sun–Thu).
    Defaults to Egypt CBE risk-free rate (~27.25% annual).
    """
    if len(returns) < 2:
        return 0.0

    daily_rf = EGX_DAILY_RF if risk_free_rate is None else risk_free_rate
    m = avg(returns)
    std = stddev(returns)

    if std == 0:
        return 0.0

    daily_sharpe = (m - daily_rf) / std

    if annualize:
        return daily_sharpe * math.sqrt(EGX_TRADING_DAYS_PER_YEAR)
    return daily_sharpe


def sortino_ratio(returns: list, risk_free_rate: float = None) -> float:
    """
    Sortino Ratio = (avg_return - daily_rf) / downside_deviation
    Only penalizes negative returns. Annualized with EGX 247-day calendar.
    """
    if len(returns) < 2:
        return 0.0

    daily_rf = EGX_DAILY_RF if risk_free_rate is None else risk_free_rate
    m = avg(returns)
    downside = [r for r in returns if r < 0]

    if not downside:
        return 99.9  # No losses → excellent

    downside_std = stddev(downside)
    if downside_std == 0:
        return 99.9

    return ((m - daily_rf) / downside_std) * math.sqrt(EGX_TRADING_DAYS_PER_YEAR)


def max_drawdown(returns: list) -> float:
    """
    Maximum peak-to-trough decline in cumulative returns.
    Returns as negative percentage.
    """
    if not returns:
        return 0.0

    cumulative = []
    running = 0
    for r in returns:
        running += r
        cumulative.append(running)

    peak = cumulative[0]
    max_dd = 0

    for val in cumulative:
        if val > peak:
            peak = val
        dd = val - peak
        if dd < max_dd:
            max_dd = dd

    return max_dd


def profit_factor(returns: list) -> float:
    """
    Profit Factor = sum(wins) / |sum(losses)|
    > 1.0 means profitable, > 2.0 is excellent.
    """
    gains = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))

    if losses == 0:
        return 99.9 if gains > 0 else 0.0

    return gains / losses


def cumulative_return(returns: list) -> float:
    """Cumulative return from a series of percentage returns."""
    if not returns:
        return 0.0

    cumulative = 1.0
    for r in returns:
        cumulative *= (1 + r / 100)

    return (cumulative - 1) * 100


# ─── ROLLING WINDOWS ──────────────────────────────────────────

def get_rolling_metrics(user_id: int = None, windows: list = None) -> dict:
    """
    Returns performance metrics for multiple rolling windows.
    Used for the dashboard sparkline and trend display.
    """
    if windows is None:
        windows = [30, 60, 90]

    results = {}
    for w in windows:
        metrics = get_performance_summary(user_id=user_id, days=w, live_only=True)
        results[f"{w}d"] = {
            "win_rate": metrics["win_rate"],
            "sharpe": metrics["sharpe_ratio"],
            "avg_return": metrics["avg_return_1d"],
            "total_trades": metrics["total_predictions"],
            "max_drawdown": metrics["max_drawdown"],
            "alpha": metrics["avg_alpha_1d"]
        }
    return results


# ─── PER-AGENT METRICS ────────────────────────────────────────

def get_agent_comparison(days: int = 90) -> list:
    """
    Compare all agents' accuracy over the given window.
    Uses agent_performance_daily snapshots.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            result = _query(cursor, """
                SELECT
                    agent_name,
                    predictions_30d, correct_30d, win_rate_30d,
                    avg_confidence_30d,
                    predictions_90d, correct_90d, win_rate_90d
                FROM agent_performance_daily
                WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM agent_performance_daily)
                ORDER BY win_rate_30d DESC NULLS LAST
            """)
        except Exception:
            return []

        return [
            {
                "agent": r["agent_name"],
                "predictions_30d": int(r.get("predictions_30d", 0) or 0),
                "win_rate_30d": float(r.get("win_rate_30d", 0) or 0),
                "avg_confidence_30d": float(r.get("avg_confidence_30d", 0) or 0),
                "predictions_90d": int(r.get("predictions_90d", 0) or 0),
                "win_rate_90d": float(r.get("win_rate_90d", 0) or 0),
            }
            for r in result
        ]


# ─── PER-STOCK METRICS ────────────────────────────────────────

def get_stock_performance(days: int = 90) -> list:
    """
    Performance breakdown per stock.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        if DATABASE_URL:
            live_filter = f"(tr.is_live = {sql_bool(True)} OR tr.is_live IS NULL) AND (tr.is_simulated = {sql_bool(False)} OR tr.is_simulated IS NULL)"
            date_filter = sql_days_ago("tr.recommendation_date", placeholder="%s")
        else:
            live_filter = f"(tr.is_live = {sql_bool(True)} OR tr.is_live IS NULL) AND (tr.is_simulated = {sql_bool(False)} OR tr.is_simulated IS NULL)"
            date_filter = sql_days_ago("tr.recommendation_date", placeholder="?")

        # Try joining with egx30_stocks for names; fallback if table not available
        try:
            result = _query(cursor, f"""
                SELECT
                    tr.symbol, s.name_en, s.sector_en,
                    COUNT(*) AS total_recs,
                    SUM(CASE WHEN tr.was_correct = {sql_bool(True)} THEN 1 ELSE 0 END) AS correct,
                    {'ROUND(AVG(tr.actual_next_day_return)::numeric, 3)' if DATABASE_URL else 'ROUND(AVG(tr.actual_next_day_return), 3)'} AS avg_return,
                    {'ROUND(AVG(tr.alpha_1d)::numeric, 3)' if DATABASE_URL else 'ROUND(AVG(tr.alpha_1d), 3)'} AS avg_alpha,
                    {'ROUND((SUM(CASE WHEN tr.was_correct = TRUE THEN 1 ELSE 0 END))::numeric / NULLIF(COUNT(*), 0) * 100, 1)' if DATABASE_URL else 'ROUND(CAST(SUM(CASE WHEN tr.was_correct = 1 THEN 1 ELSE 0 END) AS REAL) / NULLIF(COUNT(*), 0) * 100, 1)'} AS win_rate
                FROM trade_recommendations tr
                LEFT JOIN egx30_stocks s ON tr.symbol = s.symbol
                WHERE tr.was_correct IS NOT NULL
                AND {live_filter}
                AND {date_filter}
                GROUP BY tr.symbol, s.name_en, s.sector_en
                HAVING COUNT(*) >= 3
                ORDER BY avg_alpha DESC
            """, [days])
        except Exception:
            result = []

        return [dict(r) for r in result]


# ─── EQUITY CURVE DATA ────────────────────────────────────────

def get_equity_curve(user_id: int = None, days: int = 180) -> dict:
    """
    Daily cumulative returns for equity curve chart.
    Returns both Xmore and EGX30 series for overlay.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        conditions = [
            "tr.actual_next_day_return IS NOT NULL"
        ]
        params = []

        if DATABASE_URL:
            conditions.append(f"(tr.is_live = {sql_bool(True)} OR tr.is_live IS NULL)")
            conditions.append(f"(tr.is_simulated = {sql_bool(False)} OR tr.is_simulated IS NULL)")
            conditions.append(sql_days_ago("tr.recommendation_date", placeholder=_ph(1)))
        else:
            conditions.append(f"(tr.is_live = {sql_bool(True)} OR tr.is_live IS NULL)")
            conditions.append(f"(tr.is_simulated = {sql_bool(False)} OR tr.is_simulated IS NULL)")
            conditions.append(sql_days_ago("tr.recommendation_date", placeholder=_ph(1)))
        params.append(days)

        if user_id:
            conditions.append(f"tr.user_id = {_ph(len(params)+1)}")
            params.append(user_id)

        where = " AND ".join(conditions)

        try:
            if DATABASE_URL:
                daily = _query(cursor, f"""
                    SELECT
                        tr.recommendation_date AS date,
                        ROUND(AVG(tr.actual_next_day_return)::numeric, 4) AS xmore_return,
                        ROUND(AVG(tr.benchmark_1d_return)::numeric, 4) AS benchmark_return
                    FROM trade_recommendations tr
                    WHERE {where}
                    GROUP BY tr.recommendation_date
                    ORDER BY tr.recommendation_date ASC
                """, params)
            else:
                daily = _query(cursor, f"""
                    SELECT
                        tr.recommendation_date AS date,
                        ROUND(AVG(tr.actual_next_day_return), 4) AS xmore_return,
                        ROUND(AVG(tr.benchmark_1d_return), 4) AS benchmark_return
                    FROM trade_recommendations tr
                    WHERE {where}
                    GROUP BY tr.recommendation_date
                    ORDER BY tr.recommendation_date ASC
                """, params)
        except Exception:
            return {"series": [], "total_xmore": 0, "total_egx30": 0, "total_alpha": 0}

        # Build cumulative series
        xmore_cum = 0
        bench_cum = 0
        series = []

        for d in daily:
            xmore_cum += float(d.get("xmore_return", 0) or 0)
            bench_cum += float(d.get("benchmark_return", 0) or 0)
            series.append({
                "date": str(d["date"]),
                "xmore": round(xmore_cum, 2),
                "egx30": round(bench_cum, 2),
                "alpha": round(xmore_cum - bench_cum, 2)
            })

        return {
            "series": series,
            "total_xmore": round(xmore_cum, 2),
            "total_egx30": round(bench_cum, 2),
            "total_alpha": round(xmore_cum - bench_cum, 2)
        }


# ─── INSTITUTIONAL METRICS ────────────────────────────────────

def calculate_calmar_ratio(returns: list, max_dd: float) -> float:
    """
    Calmar Ratio = Annualized Return / Absolute Max Drawdown.
    Returns 0.0 if max_dd is 0. Returns None if fewer than 20 data points.
    """
    if len(returns) < 20:
        return None
    if not max_dd:
        return 0.0
    mean_daily = avg(returns)
    annual_return = (1 + mean_daily) ** EGX_TRADING_DAYS_PER_YEAR - 1
    return round(annual_return / abs(max_dd), 4)


def calculate_max_drawdown_details(equity_curve: list) -> dict:
    """
    Detailed drawdown analysis: peak, trough, recovery, duration.
    equity_curve: list of cumulative portfolio values (not returns).
    """
    if not equity_curve or len(equity_curve) < 2:
        return {
            "max_drawdown_pct": 0.0, "drawdown_start_idx": None,
            "drawdown_end_idx": None, "recovery_idx": None,
            "drawdown_duration_days": 0, "recovery_duration_days": None,
            "is_recovered": False,
        }

    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0.0
    dd_start = 0
    dd_end = 0

    for i, val in enumerate(equity_curve):
        if val > peak:
            peak = val
            peak_idx = i
        dd_pct = (val - peak) / peak if peak != 0 else 0
        if dd_pct < max_dd:
            max_dd = dd_pct
            dd_start = peak_idx
            dd_end = i

    # Find recovery index (new peak after trough)
    recovery_idx = None
    recovery_duration = None
    trough_val = equity_curve[dd_start] * (1 + max_dd)  # approximate peak value
    pre_dd_peak = equity_curve[dd_start]
    for i in range(dd_end + 1, len(equity_curve)):
        if equity_curve[i] >= pre_dd_peak:
            recovery_idx = i
            recovery_duration = recovery_idx - dd_end
            break

    return {
        "max_drawdown_pct": round(max_dd, 6),
        "drawdown_start_idx": dd_start,
        "drawdown_end_idx": dd_end,
        "recovery_idx": recovery_idx,
        "drawdown_duration_days": dd_end - dd_start,
        "recovery_duration_days": recovery_duration,
        "is_recovered": recovery_idx is not None,
    }


def calculate_rolling_sharpe(returns: list, window: int = 30) -> list:
    """Rolling Sharpe ratio over `window` EGX trading days."""
    if len(returns) < window:
        return []
    result = []
    for i in range(window, len(returns) + 1):
        window_returns = returns[i - window:i]
        s = sharpe_ratio(window_returns)
        result.append({"day_index": i - 1, "sharpe": round(s, 4)})
    return result


def calculate_win_loss_ratio(trades: list) -> dict:
    """
    Detailed win/loss analysis from a list of trade dicts with 'return_pct'.
    """
    if not trades:
        return {
            "win_rate": 0, "avg_win_pct": 0, "avg_loss_pct": 0,
            "win_loss_ratio": 0, "profit_factor": 0, "expectancy_pct": 0,
            "largest_win_pct": 0, "largest_loss_pct": 0,
            "consecutive_wins_max": 0, "consecutive_losses_max": 0,
        }

    returns = [float(t.get("return_pct") or t.get("actual_next_day_return") or 0) for t in trades]
    wins  = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    total = len(returns)

    win_rate   = len(wins) / total if total else 0
    loss_rate  = 1 - win_rate
    avg_win    = avg(wins) if wins else 0
    avg_loss   = avg(losses) if losses else 0
    wl_ratio   = abs(avg_win / avg_loss) if avg_loss != 0 else 99.9 if avg_win > 0 else 0
    gross_wins = sum(wins)
    gross_loss = abs(sum(losses))
    pf         = gross_wins / gross_loss if gross_loss > 0 else (99.9 if gross_wins > 0 else 0)
    expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)

    # Consecutive streaks
    max_wins = max_losses = cur_wins = cur_losses = 0
    for r in returns:
        if r > 0:
            cur_wins += 1
            cur_losses = 0
            max_wins = max(max_wins, cur_wins)
        elif r < 0:
            cur_losses += 1
            cur_wins = 0
            max_losses = max(max_losses, cur_losses)
        else:
            cur_wins = cur_losses = 0

    return {
        "win_rate":            round(win_rate, 4),
        "avg_win_pct":         round(avg_win, 4),
        "avg_loss_pct":        round(avg_loss, 4),
        "win_loss_ratio":      round(wl_ratio, 4),
        "profit_factor":       round(pf, 4),
        "expectancy_pct":      round(expectancy, 4),
        "largest_win_pct":     round(max(wins), 4) if wins else 0,
        "largest_loss_pct":    round(min(losses), 4) if losses else 0,
        "consecutive_wins_max": max_wins,
        "consecutive_losses_max": max_losses,
    }


def calculate_benchmark_comparison(portfolio_returns: list, benchmark_returns: list) -> dict:
    """Alpha, beta, information ratio, up/down capture vs EGX30."""
    if not portfolio_returns or not benchmark_returns:
        return {
            "portfolio_total_return": 0, "benchmark_total_return": 0,
            "alpha_total": 0, "alpha_annualized": 0, "beta": 0,
            "correlation": 0, "information_ratio": 0, "tracking_error": 0,
            "up_capture": 0, "down_capture": 0, "outperformance_days_pct": 0,
        }

    n = min(len(portfolio_returns), len(benchmark_returns))
    p = portfolio_returns[:n]
    b = benchmark_returns[:n]

    p_total = cumulative_return(p)
    b_total = cumulative_return(b)

    excess = [pi - bi for pi, bi in zip(p, b)]
    te = stddev(excess)
    ir = (avg(excess) / te * math.sqrt(EGX_TRADING_DAYS_PER_YEAR)) if te > 0 else 0

    # Beta
    mean_p, mean_b = avg(p), avg(b)
    cov = sum((pi - mean_p) * (bi - mean_b) for pi, bi in zip(p, b)) / max(n - 1, 1)
    var_b = stddev(b) ** 2
    beta = cov / var_b if var_b > 0 else 0

    # Pearson correlation
    std_p, std_b = stddev(p), stddev(b)
    corr = (cov / (std_p * std_b)) if std_p > 0 and std_b > 0 else 0

    # Alpha annualized
    mean_daily_p = avg(p)
    mean_daily_b = avg(b)
    annual_p = (1 + mean_daily_p) ** EGX_TRADING_DAYS_PER_YEAR - 1
    annual_b = (1 + mean_daily_b) ** EGX_TRADING_DAYS_PER_YEAR - 1
    alpha_annual = annual_p - annual_b

    # Up/down capture
    up_days   = [(pi, bi) for pi, bi in zip(p, b) if bi > 0]
    down_days = [(pi, bi) for pi, bi in zip(p, b) if bi < 0]
    up_capture   = (avg([pi for pi, _ in up_days]) / avg([bi for _, bi in up_days])) if up_days else 0
    down_capture = (avg([pi for pi, _ in down_days]) / avg([bi for _, bi in down_days])) if down_days else 0

    outperform_pct = sum(1 for e in excess if e > 0) / n if n > 0 else 0

    return {
        "portfolio_total_return":  round(p_total, 4),
        "benchmark_total_return":  round(b_total, 4),
        "alpha_total":             round(p_total - b_total, 4),
        "alpha_annualized":        round(alpha_annual, 4),
        "beta":                    round(beta, 4),
        "correlation":             round(corr, 4),
        "information_ratio":       round(ir, 4),
        "tracking_error":          round(te * math.sqrt(EGX_TRADING_DAYS_PER_YEAR), 4),
        "up_capture":              round(up_capture, 4),
        "down_capture":            round(down_capture, 4),
        "outperformance_days_pct": round(outperform_pct, 4),
    }


def generate_full_metrics_report(db_connection, days: int = 90) -> dict:
    """
    Master function: computes and returns all institutional metrics in one call.
    """
    cursor = db_connection.cursor()

    if DATABASE_URL:
        date_filter = sql_days_ago("recommendation_date", days=days)
        live_filter = f"(is_live = {sql_bool(True)} OR is_live IS NULL)"
        sim_filter  = f"(is_simulated = {sql_bool(False)} OR is_simulated IS NULL)"
    else:
        date_filter = sql_days_ago("recommendation_date", days=days)
        live_filter = f"(is_live = {sql_bool(True)} OR is_live IS NULL)"
        sim_filter  = f"(is_simulated = {sql_bool(False)} OR is_simulated IS NULL)"

    # Count live vs simulated for data_transparency reporting
    try:
        cursor.execute(f"""
            SELECT
                SUM(CASE WHEN {sim_filter} THEN 1 ELSE 0 END) AS live_cnt,
                SUM(CASE WHEN is_simulated = {sql_bool(True)} THEN 1 ELSE 0 END) AS sim_cnt,
                MIN(CASE WHEN {sim_filter} THEN recommendation_date END) AS earliest_live
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND {live_filter}
            AND {date_filter}
        """)
        tc_row = cursor.fetchone()
        _live_count = int(tc_row[0] or 0)
        _sim_count  = int(tc_row[1] or 0)
        _earliest_live = str(tc_row[2]) if tc_row[2] else None
    except Exception:
        _live_count, _sim_count, _earliest_live = 0, 0, None

    if _sim_count > 0:
        import logging as _log
        _log.getLogger(__name__).warning(
            f"[METRICS] {_sim_count} simulated predictions found. "
            f"EXCLUDED from all investor-facing metric calculations. "
            f"Only {_live_count} live predictions are used."
        )

    try:
        cursor.execute(f"""
            SELECT recommendation_date, actual_next_day_return,
                   benchmark_1d_return, alpha_1d, was_correct,
                   round_trip_cost_egp, position_value_egp
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND {live_filter}
            AND {sim_filter}
            AND {date_filter}
            ORDER BY recommendation_date ASC
        """)
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) if not isinstance(r, dict) else r for r in cursor.fetchall()]
    except Exception:
        rows = []

    trade_count = len(rows)
    returns_1d  = [float(r["actual_next_day_return"]) for r in rows if r.get("actual_next_day_return") is not None]
    bench_1d    = [float(r["benchmark_1d_return"]) for r in rows if r.get("benchmark_1d_return") is not None]

    # Build cost-per-trade list for net metrics
    costs_pct_full = []
    for r in rows:
        if r.get("actual_next_day_return") is None:
            continue
        rtc = r.get("round_trip_cost_egp")
        pve = r.get("position_value_egp")
        if rtc and pve and float(pve) > 0:
            costs_pct_full.append(float(rtc) / float(pve) * 100)
        else:
            costs_pct_full.append(EGX_ROUND_TRIP_RATE * 100)
    returns_1d_net = apply_transaction_costs(returns_1d, costs_pct_full)
    cost_drag_total = sum(costs_pct_full) if costs_pct_full else 0.0
    profitability_accuracy_full = (
        round(sum(1 for r in returns_1d_net if r > 0) / len(returns_1d_net) * 100, 1)
        if returns_1d_net else 0
    )

    # Data quality warnings
    warnings = []
    if trade_count < MINIMUM_TRADES_FOR_METRICS:
        warnings.append(
            f"Only {trade_count} completed trades. "
            f"Minimum {MINIMUM_TRADES_FOR_METRICS} required for reliable ratio calculations. "
            f"Displayed metrics are indicative only."
        )
    if days < 60:
        warnings.append(
            "Performance period under 60 days. "
            "Annualized figures may be misleading for short periods."
        )

    # Build equity curve for drawdown details
    equity_curve = []
    running = 100.0
    for r in returns_1d:
        running *= (1 + r / 100)
        equity_curve.append(running)

    # Collect trade dicts for win/loss
    trades_for_wl = [
        {"return_pct": float(r["actual_next_day_return"])}
        for r in rows if r.get("actual_next_day_return") is not None
    ]

    mdd = max_drawdown(returns_1d)
    mdd_details = calculate_max_drawdown_details(equity_curve)
    sr  = sharpe_ratio(returns_1d)
    so  = sortino_ratio(returns_1d)
    cal = calculate_calmar_ratio(returns_1d, abs(mdd)) if returns_1d else None
    rolling_sh = calculate_rolling_sharpe(returns_1d, window=30)
    wl  = calculate_win_loss_ratio(trades_for_wl)
    bench = calculate_benchmark_comparison(returns_1d, bench_1d) if bench_1d else {}

    sr_net  = sharpe_ratio(returns_1d_net)
    so_net  = sortino_ratio(returns_1d_net)
    mdd_net = max_drawdown(returns_1d_net)
    pf_net  = profit_factor(returns_1d_net)

    return {
        "period_days":          days,
        "generated_at":         datetime.now(timezone.utc).isoformat() + "Z",
        "trade_count":          trade_count,
        # Gross metrics (price movement only)
        "sharpe_ratio":         round(sr, 4),
        "sortino_ratio":        round(so, 4),
        "calmar_ratio":         round(cal, 4) if cal is not None else None,
        "max_drawdown":         mdd_details,
        "rolling_sharpe_30d":   rolling_sh,
        "win_loss":             wl,
        "benchmark":            bench,
        # Net (cost-adjusted) metrics — primary reporting metrics
        "sharpe_ratio_net":     round(sr_net, 4),
        "sortino_ratio_net":    round(so_net, 4),
        "max_drawdown_net":     round(mdd_net, 4),
        "profit_factor_net":    round(pf_net, 4),
        "avg_return_net":       round(avg(returns_1d_net), 4),
        "cost_drag_total_pct":  round(cost_drag_total, 2),
        "profitability_accuracy": profitability_accuracy_full,
        "risk_free_rate_used":  EGX_RISK_FREE_RATE_ANNUAL,
        "minimum_trades_met":   trade_count >= MINIMUM_TRADES_FOR_METRICS,
        "data_quality_warning": " | ".join(warnings),
        "data_transparency": {
            "live_signals_count":         _live_count,
            "simulated_signals_excluded": _sim_count,
            "metrics_basis":              "live_only",
            "earliest_live_signal_date":  _earliest_live,
        },
    }


# ─── HELPERS ──────────────────────────────────────────────────

def get_execution_filter_stats(days: int = 30) -> dict:
    """
    P8: Report what fraction of signals are blocked by the edge-ratio filter
    or require order splitting. Alerts if > 40% are blocked.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        ph = '%s' if DATABASE_URL else '?'
        if DATABASE_URL:
            date_part = sql_days_ago("recommendation_date", placeholder=ph)
            approved_val = sql_bool(True)
            blocked_val  = sql_bool(False)
            split_val    = sql_bool(True)
        else:
            date_part = sql_days_ago("recommendation_date", placeholder=ph)
            approved_val = sql_bool(True)
            blocked_val  = sql_bool(False)
            split_val    = sql_bool(True)
        try:
            rows = _query(cursor, f"""
                SELECT
                    COUNT(*) AS total_signals,
                    SUM(CASE WHEN execution_approved = {approved_val} THEN 1 ELSE 0 END) AS approved_count,
                    SUM(CASE WHEN execution_approved = {blocked_val} THEN 1 ELSE 0 END) AS blocked_count,
                    SUM(CASE WHEN split_required = {split_val} THEN 1 ELSE 0 END) AS split_count,
                    AVG(edge_ratio) AS avg_edge_ratio,
                    MIN(edge_ratio) AS min_edge_ratio,
                    MAX(edge_ratio) AS max_edge_ratio
                FROM trade_recommendations
                WHERE {date_part}
                AND execution_approved IS NOT NULL
            """, [days])
            row = rows[0] if rows else {}
            total   = int(row.get("total_signals") or 0)
            blocked = int(row.get("blocked_count") or 0)
            return {
                "total": total,
                "approved": int(row.get("approved_count") or 0),
                "blocked_by_edge": blocked,
                "blocked_pct": round(blocked / total * 100, 1) if total else 0,
                "split_required": int(row.get("split_count") or 0),
                "avg_edge_ratio": round(float(row.get("avg_edge_ratio") or 0), 2),
                "min_edge_ratio": round(float(row.get("min_edge_ratio") or 0), 2),
                "max_edge_ratio": round(float(row.get("max_edge_ratio") or 0), 2),
                "period_days": days,
            }
        except Exception:
            return {
                "total": 0, "approved": 0, "blocked_by_edge": 0, "blocked_pct": 0,
                "split_required": 0, "avg_edge_ratio": 0, "min_edge_ratio": 0,
                "max_edge_ratio": 0, "period_days": days,
            }


def avg(lst: list) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def stddev(lst: list) -> float:
    if len(lst) < 2:
        return 0.0
    m = avg(lst)
    return math.sqrt(sum((x - m) ** 2 for x in lst) / (len(lst) - 1))


def empty_metrics() -> dict:
    return {
        "total_predictions": 0, "resolved": 0, "wins": 0, "losses": 0,
        "win_rate": 0, "avg_return_1d": 0, "avg_return_5d": 0,
        "cumulative_return": 0, "sharpe_ratio": 0, "sortino_ratio": 0,
        "max_drawdown": 0, "volatility": 0, "profit_factor": 0,
        "avg_alpha_1d": 0, "avg_benchmark_1d": 0, "cumulative_alpha": 0,
        "beat_benchmark_pct": 0, "best_trade": 0, "worst_trade": 0,
        # Net / cost-adjusted metrics
        "avg_return_1d_net": 0, "cumulative_return_net": 0,
        "sharpe_ratio_net": 0, "sortino_ratio_net": 0,
        "max_drawdown_net": 0, "profit_factor_net": 0,
        "profitability_accuracy": 0, "cost_drag_total_pct": 0, "avg_cost_per_trade_pct": 0,
        "meets_minimum": False, "live_trade_count": 0,
        "first_prediction": None, "last_prediction": None,
        "period_days": 0, "live_only": True
    }
