"""
Time Machine Backtest Engine
Takes signals + price data → simulates portfolio → returns full result.
Everything runs in-memory. Nothing touches the database.

Rules:
- Max 10 concurrent positions
- No single position > 25% of portfolio value
- Minimum 10% cash reserve at all times
- Position sizing by conviction:
  consensus >= 0.75: up to 20% of portfolio
  consensus >= 0.50: up to 15%
- Exit when: stop_loss hit, target hit, or 30-day holding limit
- Daily portfolio valuation for equity curve
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _mean(arr):
    if not arr:
        return 0
    return sum(arr) / len(arr)


def _std(arr):
    if len(arr) < 2:
        return 0
    m = _mean(arr)
    return (sum((x - m) ** 2 for x in arr) / len(arr)) ** 0.5


def _parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d')


def _get_price_on_date(prices, date):
    """Get close price on a given date, or nearest prior date."""
    # Binary search-style: find exact or nearest prior
    best = None
    for p in prices:
        if p['date'] <= date:
            best = p['close']
        else:
            break
    return best


def _sum_holdings_value(holdings, price_data, day):
    """Total market value of all open positions."""
    total = 0
    for symbol, pos in holdings.items():
        prices = price_data.get(symbol, [])
        price = _get_price_on_date(prices, day)
        if price:
            total += pos['shares'] * price
    return total


def _get_all_trading_days(price_data, start_date):
    """Get sorted list of all unique trading days from start_date onward."""
    days = set()
    for symbol, prices in price_data.items():
        for p in prices:
            if p['date'] >= start_date:
                days.add(p['date'])
    return sorted(days)


def _compute_monthly_breakdown(equity_curve, initial_amount):
    """Compute monthly return breakdown from equity curve."""
    if not equity_curve:
        return []

    months = {}
    for point in equity_curve:
        month_key = point['date'][:7]  # "YYYY-MM"
        months[month_key] = point

    monthly = []
    sorted_months = sorted(months.keys())
    prev_value = initial_amount
    prev_egx = initial_amount

    for month_key in sorted_months:
        point = months[month_key]
        ret_pct = round(((point['value'] - prev_value) / prev_value) * 100, 2) if prev_value > 0 else 0
        egx_ret = None
        if point.get('tasi_value') is not None and prev_egx > 0:
            egx_ret = round(((point['tasi_value'] - prev_egx) / prev_egx) * 100, 2)

        monthly.append({
            'month': month_key,
            'return_pct': ret_pct,
            'tasi_return_pct': egx_ret,
        })
        prev_value = point['value']
        if point.get('egx30_value') is not None:
            prev_egx = point['tasi_value']

    return monthly


def _build_allocation_timeline(completed_trades, stock_names_fn):
    """Build chronological timeline of buy/sell events."""
    events = []
    for tr in completed_trades:
        symbol = tr['stock_symbol']
        clean_symbol = symbol.replace('.SR', '').replace('.CA', '')

        # BUY event
        events.append({
            'date': tr['buy_date'],
            'event': 'BUY',
            'stock': symbol,
            'amount_egp': round(tr['buy_price'] * tr['shares'], 2),
            'reason_en': f"BUY {clean_symbol} — consensus {tr.get('consensus_score', 'N/A')}",
            'reason_ar': f"شراء {clean_symbol} — إجماع {tr.get('consensus_score', 'N/A')}",
        })

        # SELL event
        reason_map = {
            'stop_loss': ('Stop loss triggered', 'تفعيل وقف الخسارة'),
            'target_hit': ('Target price reached', 'وصل سعر الهدف'),
            'timeout': ('30-day holding limit', 'انتهاء مدة ٣٠ يوم'),
            'still_holding': ('End of period (force-close)', 'نهاية الفترة (إغلاق إجباري)'),
        }
        reason = reason_map.get(tr.get('exit_reason'), ('Sold', 'بيع'))
        events.append({
            'date': tr['sell_date'],
            'event': 'SELL',
            'stock': symbol,
            'amount_egp': round(tr['sell_price'] * tr['shares'], 2),
            'reason_en': f"SELL {clean_symbol} — {reason[0]} ({tr['return_pct']:+.1f}%)",
            'reason_ar': f"بيع {clean_symbol} — {reason[1]} ({tr['return_pct']:+.1f}%)",
        })

    events.sort(key=lambda e: (e['date'], 0 if e['event'] == 'BUY' else 1))
    return events


def _format_duration(days):
    """Format duration in human-readable form."""
    if days < 30:
        return (f"{days} days", f"{days} يوم")
    months = days // 30
    remaining_days = days % 30
    if remaining_days == 0:
        return (f"{months} months", f"{months} أشهر")
    return (f"{months} months, {remaining_days} days", f"{months} أشهر و {remaining_days} يوم")


def run_simulation(amount: float, start_date: str, signals: list, price_data: dict,
                   stock_names_fn=None) -> dict:
    """
    Core day-by-day portfolio simulation.

    Returns full simulation result dict matching the frontend expected format.
    """
    cash = amount
    holdings = {}   # symbol -> {shares, buy_price, buy_date, stop_loss, target, signal}
    equity_curve = []
    completed_trades = []

    trading_days = _get_all_trading_days(price_data, start_date)
    if not trading_days:
        return {'error': True, 'message_en': 'No trading days found in this period.',
                'message_ar': 'لم يتم العثور على أيام تداول في هذه الفترة.'}

    # TASI baseline for benchmark
    egx30_data = price_data.get('^TASI', [])
    egx30_start = _get_price_on_date(egx30_data, start_date)

    # Build signals lookup: date -> [signals sorted by consensus DESC]
    signals_by_date = {}
    for s in signals:
        signals_by_date.setdefault(s['date'], []).append(s)

    for day in trading_days:
        portfolio_value = cash + _sum_holdings_value(holdings, price_data, day)

        # --- EXITS ---
        symbols_to_sell = []
        for symbol, pos in holdings.items():
            current_price = _get_price_on_date(price_data.get(symbol, []), day)
            if current_price is None:
                continue

            days_held = (_parse_date(day) - _parse_date(pos['buy_date'])).days
            sell_reason = None

            if current_price <= pos['stop_loss']:
                sell_reason = 'stop_loss'
            elif current_price >= pos['target']:
                sell_reason = 'target_hit'
            elif days_held >= 30:
                sell_reason = 'timeout'

            if sell_reason:
                profit = (current_price - pos['buy_price']) * pos['shares']
                return_pct = ((current_price / pos['buy_price']) - 1) * 100

                completed_trades.append({
                    'stock_symbol': symbol,
                    'stock_name_en': stock_names_fn(symbol, 'en') if stock_names_fn else symbol.replace('.SR', '').replace('.CA', ''),
                    'stock_name_ar': stock_names_fn(symbol, 'ar') if stock_names_fn else symbol.replace('.SR', '').replace('.CA', ''),
                    'action': pos['signal']['action'],
                    'buy_date': pos['buy_date'],
                    'sell_date': day,
                    'buy_price': pos['buy_price'],
                    'sell_price': round(current_price, 2),
                    'shares': pos['shares'],
                    'return_pct': round(return_pct, 2),
                    'profit_egp': round(profit, 2),
                    'holding_days': days_held,
                    'exit_reason': sell_reason,
                    'consensus_score': pos['signal']['consensus_score'],
                })
                cash += pos['shares'] * current_price
                symbols_to_sell.append(symbol)

        for s in symbols_to_sell:
            del holdings[s]

        # --- ENTRIES ---
        today_signals = signals_by_date.get(day, [])
        today_signals.sort(key=lambda x: x['consensus_score'], reverse=True)

        for signal in today_signals:
            symbol = signal['stock_symbol']
            if symbol in holdings:
                continue  # Already holding
            if len(holdings) >= 10:
                break  # Max positions

            portfolio_value = cash + _sum_holdings_value(holdings, price_data, day)
            min_cash = 0.10 * portfolio_value

            # Position sizing
            max_pct = 0.20 if signal['consensus_score'] >= 0.75 else 0.15

            max_position = min(
                max_pct * portfolio_value,
                0.25 * portfolio_value  # Hard cap
            )
            available = cash - min_cash
            position_size = min(max_position, available)

            if position_size < 1000:
                continue  # Too small

            entry_price = signal['entry_price']
            shares = int(position_size / entry_price)
            if shares < 1:
                continue

            actual_cost = shares * entry_price
            cash -= actual_cost

            holdings[symbol] = {
                'shares': shares,
                'buy_price': entry_price,
                'buy_date': day,
                'stop_loss': signal['stop_loss_price'],
                'target': signal['target_price'],
                'signal': signal,
            }

        # --- DAILY SNAPSHOT ---
        portfolio_value = cash + _sum_holdings_value(holdings, price_data, day)
        egx30_today = _get_price_on_date(egx30_data, day)
        egx30_value = amount * (egx30_today / egx30_start) if egx30_start and egx30_today else None

        equity_curve.append({
            'date': day,
            'value': round(portfolio_value, 2),
            'tasi_value': round(egx30_value, 2) if egx30_value is not None else None,
        })

    # --- FORCE-CLOSE remaining holdings at last day's price ---
    last_day = trading_days[-1] if trading_days else start_date
    for symbol, pos in list(holdings.items()):
        current_price = _get_price_on_date(price_data.get(symbol, []), last_day)
        if current_price:
            profit = (current_price - pos['buy_price']) * pos['shares']
            return_pct = ((current_price / pos['buy_price']) - 1) * 100
            completed_trades.append({
                'stock_symbol': symbol,
                'stock_name_en': stock_names_fn(symbol, 'en') if stock_names_fn else symbol.replace('.SR', '').replace('.CA', ''),
                'stock_name_ar': stock_names_fn(symbol, 'ar') if stock_names_fn else symbol.replace('.SR', '').replace('.CA', ''),
                'action': pos['signal']['action'],
                'buy_date': pos['buy_date'],
                'sell_date': last_day,
                'buy_price': pos['buy_price'],
                'sell_price': round(current_price, 2),
                'shares': pos['shares'],
                'return_pct': round(return_pct, 2),
                'profit_egp': round(profit, 2),
                'holding_days': (_parse_date(last_day) - _parse_date(pos['buy_date'])).days,
                'exit_reason': 'still_holding',
                'consensus_score': pos['signal']['consensus_score'],
            })
            cash += pos['shares'] * current_price

    holdings.clear()

    # --- COMPUTE FINAL METRICS ---
    final_value = cash
    total_return_pct = ((final_value / amount) - 1) * 100
    total_return_egp = final_value - amount
    duration_days = (_parse_date(last_day) - _parse_date(start_date)).days

    # Annualized return
    if duration_days > 0:
        annualized = ((final_value / amount) ** (365 / duration_days) - 1) * 100
    else:
        annualized = 0

    # Benchmark
    egx30_end = _get_price_on_date(egx30_data, last_day) or egx30_start
    egx30_return_pct = ((egx30_end / egx30_start) - 1) * 100 if egx30_start and egx30_end else 0
    egx30_final = amount * (1 + egx30_return_pct / 100)

    # Win/loss stats
    wins = [t for t in completed_trades if t['return_pct'] > 0]
    losses = [t for t in completed_trades if t['return_pct'] <= 0]
    win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0

    # Max drawdown from equity curve
    peak = amount
    max_dd = 0
    max_dd_date = start_date
    for point in equity_curve:
        if point['value'] > peak:
            peak = point['value']
        dd = ((point['value'] - peak) / peak) * 100
        if dd < max_dd:
            max_dd = dd
            max_dd_date = point['date']

    # Sharpe ratio (daily returns, annualized)
    sharpe = 0
    if len(equity_curve) > 1:
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]['value']
            curr = equity_curve[i]['value']
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
        if daily_returns:
            mean_fn = np.mean if HAS_NUMPY else _mean
            std_fn = np.std if HAS_NUMPY else _std
            mean_r = float(mean_fn(daily_returns))
            std_r = float(std_fn(daily_returns))
            sharpe = (mean_r / std_r) * (252 ** 0.5) if std_r > 0 else 0

    # Top and worst trades
    sorted_trades = sorted(completed_trades, key=lambda t: t['profit_egp'], reverse=True)
    top_trades = sorted_trades[:5]
    worst_trades = sorted_trades[-3:] if len(sorted_trades) >= 3 else sorted_trades

    # Monthly breakdown
    monthly = _compute_monthly_breakdown(equity_curve, amount)

    # Allocation timeline
    timeline = _build_allocation_timeline(completed_trades, stock_names_fn)

    # Duration display
    dur_en, dur_ar = _format_duration(duration_days)

    return {
        'simulation': {
            'input_amount': amount,
            'start_date': start_date,
            'end_date': last_day,
            'duration_days': duration_days,
            'duration_display_en': dur_en,
            'duration_display_ar': dur_ar,

            'final_value': round(final_value, 2),
            'total_return_pct': round(total_return_pct, 2),
            'total_return_egp': round(total_return_egp, 2),
            'annualized_return_pct': round(annualized, 2),

            'benchmark': {
                'tasi_return_pct': round(egx30_return_pct, 2),
                'tasi_final_value': round(egx30_final, 2),
                'alpha_pct': round(total_return_pct - egx30_return_pct, 2),
                'alpha_sar': round(total_return_egp - (egx30_final - amount), 2),
            },

            'risk_metrics': {
                'max_drawdown_pct': round(max_dd, 2),
                'max_drawdown_date': max_dd_date,
                'sharpe_ratio': round(sharpe, 2),
                'win_rate_pct': round(win_rate, 2),
                'avg_holding_days': round(
                    sum(t['holding_days'] for t in completed_trades) / len(completed_trades), 1
                ) if completed_trades else 0,
                'total_trades': len(completed_trades),
                'winning_trades': len(wins),
                'losing_trades': len(losses),
            },

            'equity_curve': equity_curve,
            'top_trades': top_trades,
            'worst_trades': worst_trades,
            'monthly_breakdown': monthly,
            'allocation_timeline': timeline,
        }
    }
