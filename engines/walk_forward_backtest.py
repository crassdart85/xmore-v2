"""
Walk-Forward Backtest Engine
Tests signal accuracy on rolling out-of-sample windows.
Methodology: train on 90 days, test on 20 days, step 10 days.
"""
import os, sys, logging, json
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

try:
    from config.execution_config import EGX_ROUND_TRIP_RATE
except ImportError:
    EGX_ROUND_TRIP_RATE = 0.00725

_COST_PCT = EGX_ROUND_TRIP_RATE * 100  # percentage points per trade

WALK_FORWARD_CONFIG = {
    "train_window_days": 90,
    "test_window_days":  20,
    "step_size_days":    10,
    "min_windows":        3,
    "min_train_signals": 10,
    "min_test_signals":   3,
    "total_history_days": 180,
}

AGENTS = ['consensus', 'ma', 'rsi', 'volume', 'ml', 'gemini']

# Agent column mapping in consensus_results agent_signals_json
AGENT_COL_MAP = {
    'ma':     'MA_Crossover',
    'rsi':    'RSI_Agent',
    'volume': 'Volume_Spike',
    'ml':     'ML_RandomForest',
    'gemini': 'Gemini_LLM',
}

class InsufficientDataError(Exception):
    pass

def _is_postgres(conn):
    return hasattr(conn, 'cursor') and not hasattr(conn, 'execute') or type(conn).__module__.startswith('psycopg2')

def _run_query(conn, sql, params=None):
    """Run a SELECT, return list of dicts."""
    params = params or []
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    except Exception:
        # sqlite3 style
        import sqlite3
        cursor = conn.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

def _run_scalar(conn, sql, params=None):
    rows = _run_query(conn, sql, params or [])
    if not rows:
        return None
    return list(rows[0].values())[0]

def _execute(conn, sql, params=None):
    """Run INSERT/UPDATE/DELETE."""
    params = params or []
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    except Exception:
        conn.execute(sql, params)
        conn.commit()


class WalkForwardBacktest:
    def __init__(self, db_connection, config: dict = None):
        self.conn = db_connection
        self.cfg  = {**WALK_FORWARD_CONFIG, **(config or {})}
        self._pg  = self._detect_postgres()

    def _detect_postgres(self):
        try:
            t = type(self.conn)
            module = getattr(t, '__module__', '') or ''
            return 'psycopg2' in module
        except Exception:
            return False

    def _ph(self, n):
        return f'${n}' if self._pg else '?'

    # ── 1. Symbol list ────────────────────────────────────────
    def get_symbols_to_test(self):
        min_days = self.cfg['total_history_days']
        try:
            rows = _run_query(self.conn, f"""
                SELECT p.symbol,
                       COUNT(*) AS price_days,
                       MAX(p.date) AS last_price
                FROM prices p
                GROUP BY p.symbol
                HAVING COUNT(*) >= {min_days}
            """)
        except Exception as e:
            logger.warning(f"[WFB] get_symbols_to_test prices query failed: {e}")
            return []

        # Filter: at least 30 consensus rows
        valid = []
        for r in rows:
            sym = r['symbol']
            # Skip macro symbols
            if sym.startswith('MACRO_'):
                continue
            # Skip stale (last price > 5 trading days old = ~7 calendar days)
            try:
                last = r['last_price']
                if isinstance(last, str):
                    last = datetime.strptime(last[:10], '%Y-%m-%d').date()
                elif hasattr(last, 'date'):
                    last = last.date()
                if (date.today() - last).days > 10:
                    logger.debug(f"[WFB] Skipping {sym}: stale data ({last})")
                    continue
            except Exception:
                pass
            # Check consensus row count
            try:
                cnt = _run_scalar(self.conn, f"""
                    SELECT COUNT(*) FROM consensus_results WHERE symbol = {self._ph(1)}
                """, [sym])
                if (cnt or 0) < 30:
                    continue
            except Exception:
                pass
            valid.append(sym)
        return sorted(valid)

    # ── 2. Price history ─────────────────────────────────────
    def get_price_history(self, symbol: str, days: int) -> pd.DataFrame:
        rows = _run_query(self.conn, f"""
            SELECT date, open, high, low, close, volume
            FROM prices
            WHERE symbol = {self._ph(1)}
              AND close IS NOT NULL
            ORDER BY date ASC
        """, [symbol])
        if not rows:
            raise InsufficientDataError(f"{symbol}: no price data")
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date']).dt.date
        df = df.tail(days).reset_index(drop=True)
        if len(df) < days:
            raise InsufficientDataError(f"{symbol}: only {len(df)} price rows, need {days}")
        return df

    # ── 3. Signal history ────────────────────────────────────
    def get_signal_history(self, symbol: str, days: int) -> pd.DataFrame:
        rows = _run_query(self.conn, f"""
            SELECT
                cr.prediction_date AS date,
                cr.final_signal    AS consensus_signal,
                cr.confidence,
                cr.conviction,
                cr.agent_signals_json
            FROM consensus_results cr
            WHERE cr.symbol = {self._ph(1)}
            ORDER BY cr.prediction_date ASC
        """, [symbol])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date']).dt.date

        # Parse agent signals from JSON
        for agent_key, agent_name in AGENT_COL_MAP.items():
            def _extract(json_str, name=agent_name):
                try:
                    d = json.loads(json_str or '{}')
                    # Try direct key or nested
                    sig = d.get(name, d.get(name.lower(), {}).get('signal', 'HOLD'))
                    if isinstance(sig, dict):
                        sig = sig.get('signal', 'HOLD')
                    return str(sig).upper() if sig else 'HOLD'
                except Exception:
                    return 'HOLD'
            df[f'agent_{agent_key}'] = df['agent_signals_json'].apply(_extract)

        df = df.tail(days).reset_index(drop=True)
        return df

    # ── 4. Accuracy evaluation ───────────────────────────────
    def evaluate_signal_accuracy(self, signals: pd.DataFrame, prices: pd.DataFrame,
                                  signal_col: str = 'consensus_signal',
                                  horizon: int = 1) -> Optional[dict]:
        if signals.empty or prices.empty:
            return None

        price_map = dict(zip(prices['date'], prices['close'].astype(float)))
        price_dates = sorted(price_map.keys())

        wins, losses = [], []
        for _, row in signals.iterrows():
            sig_date = row['date']
            signal   = str(row.get(signal_col, 'HOLD')).upper()
            if signal == 'HOLD':
                continue
            if sig_date not in price_map:
                continue
            # Find exit price: horizon trading days later
            later = [d for d in price_dates if d > sig_date]
            if len(later) < horizon:
                continue
            entry = price_map[sig_date]
            exit_ = price_map[later[horizon - 1]]
            if entry <= 0:
                continue
            ret = (exit_ - entry) / entry * 100
            if signal == 'UP':
                direction_ret = ret
                win = ret > 0
            elif signal == 'DOWN':
                direction_ret = -ret
                win = ret < 0
            else:
                continue
            if win:
                wins.append(direction_ret)
            else:
                losses.append(direction_ret)

        total = len(wins) + len(losses)
        if total < self.cfg['min_test_signals']:
            return None

        gross_wins  = sum(w for w in wins  if w > 0)
        gross_loss  = abs(sum(l for l in losses if l < 0))
        pf = gross_wins / gross_loss if gross_loss > 0 else (999.0 if gross_wins > 0 else 1.0)

        all_rets = wins + losses

        # Net return: deduct round-trip cost from every traded signal
        all_rets_net = [r - _COST_PCT for r in wins] + [r - _COST_PCT for r in losses]
        net_wins  = [r for r in all_rets_net if r > 0]
        net_losses = [r for r in all_rets_net if r < 0]
        net_gross_wins = sum(net_wins)
        net_gross_loss = abs(sum(net_losses))
        pf_net = (net_gross_wins / net_gross_loss
                  if net_gross_loss > 0 else (999.0 if net_gross_wins > 0 else 0.0))

        return {
            'directional_accuracy': len(wins) / total,
            'signal_count':         total,
            'win_count':            len(wins),
            'loss_count':           len(losses),
            'avg_return_pct':       float(np.mean(all_rets)),
            'avg_return_pct_net':   float(np.mean(all_rets_net)),
            'avg_win_pct':          float(np.mean(wins))   if wins   else 0.0,
            'avg_loss_pct':         float(np.mean(losses)) if losses else 0.0,
            'profit_factor':        round(pf, 4),
            'profit_factor_net':    round(pf_net, 4),
        }

    # ── 5. Walk-forward for one symbol ───────────────────────
    def run_walk_forward_for_symbol(self, symbol: str) -> list:
        total  = self.cfg['total_history_days']
        train  = self.cfg['train_window_days']
        test   = self.cfg['test_window_days']
        step   = self.cfg['step_size_days']
        min_w  = self.cfg['min_windows']

        prices  = self.get_price_history(symbol, total)
        signals = self.get_signal_history(symbol, total)

        if signals.empty or len(signals) < train + test:
            raise InsufficientDataError(f"{symbol}: insufficient signal history ({len(signals)} rows)")

        # Walk-forward windows
        window_results = {a: [] for a in AGENTS}
        start = 0
        while start + train + test <= len(signals):
            test_sigs   = signals.iloc[start + train : start + train + test].copy()
            # Match prices by date
            test_dates  = set(test_sigs['date'])
            test_prices = prices[prices['date'].isin(test_dates)].copy()

            # Consensus
            cr = self.evaluate_signal_accuracy(test_sigs, test_prices, 'consensus_signal')
            if cr:
                window_results['consensus'].append(cr)

            # Per-agent
            for agent in AGENTS[1:]:
                col = f'agent_{agent}'
                if col in test_sigs.columns:
                    # Remap the signal column
                    tmp = test_sigs.rename(columns={col: '_sig'}).copy()
                    tmp['consensus_signal'] = tmp['_sig']
                    ar = self.evaluate_signal_accuracy(tmp, test_prices, 'consensus_signal')
                    if ar:
                        window_results[agent].append(ar)

            start += step

        # Aggregate per agent
        results = []
        for agent, windows in window_results.items():
            if len(windows) < min_w:
                continue
            accs    = [w['directional_accuracy'] for w in windows]
            rets    = [w['avg_return_pct']        for w in windows]
            rets_net = [w.get('avg_return_pct_net', w['avg_return_pct'] - _COST_PCT) for w in windows]
            pfs     = [w['profit_factor']          for w in windows]
            pfs_net = [w.get('profit_factor_net', w['profit_factor']) for w in windows]
            signals_total = sum(w['signal_count'] for w in windows)
            wins_total    = sum(w['win_count']     for w in windows)
            losses_total  = sum(w['loss_count']    for w in windows)
            results.append({
                'symbol':                  symbol,
                'agent_name':              agent,
                'methodology':             'walk_forward',
                'train_window_days':       train,
                'test_window_days':        test,
                'step_size_days':          step,
                'windows_tested':          len(windows),
                'directional_accuracy':    float(np.mean(accs)),
                'directional_accuracy_std': float(np.std(accs)) if len(accs) > 1 else 0.0,
                'signal_count_total':      signals_total,
                'win_count':               wins_total,
                'loss_count':              losses_total,
                'avg_return_pct':          float(np.mean(rets)),
                'avg_return_pct_net':      float(np.mean(rets_net)),
                'avg_win_pct':             float(np.mean([w['avg_win_pct']  for w in windows])),
                'avg_loss_pct':            float(np.mean([w['avg_loss_pct'] for w in windows])),
                'profit_factor':           float(np.mean(pfs)),
                'profit_factor_net':       float(np.mean(pfs_net)),
                'is_simulated':            False,
                'data_quality_warning':    '',
            })
        return results

    # ── 6. Save results ──────────────────────────────────────
    def save_results(self, results: list, run_date: date):
        if not results:
            return
        if self._pg:
            upsert = """
                INSERT INTO backtest_results
                    (symbol, agent_name, run_date, methodology,
                     train_window_days, test_window_days, step_size_days,
                     windows_tested, directional_accuracy, directional_accuracy_std,
                     signal_count_total, win_count, loss_count,
                     avg_return_pct, avg_win_pct, avg_loss_pct, profit_factor,
                     is_simulated, data_quality_warning, updated_at)
                VALUES
                    (%s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s, NOW())
                ON CONFLICT (symbol, agent_name, run_date) DO UPDATE SET
                    windows_tested          = EXCLUDED.windows_tested,
                    directional_accuracy    = EXCLUDED.directional_accuracy,
                    directional_accuracy_std = EXCLUDED.directional_accuracy_std,
                    signal_count_total      = EXCLUDED.signal_count_total,
                    win_count               = EXCLUDED.win_count,
                    loss_count              = EXCLUDED.loss_count,
                    avg_return_pct          = EXCLUDED.avg_return_pct,
                    avg_win_pct             = EXCLUDED.avg_win_pct,
                    avg_loss_pct            = EXCLUDED.avg_loss_pct,
                    profit_factor           = EXCLUDED.profit_factor,
                    updated_at              = NOW()
            """
        else:
            upsert = """
                INSERT OR REPLACE INTO backtest_results
                    (symbol, agent_name, run_date, methodology,
                     train_window_days, test_window_days, step_size_days,
                     windows_tested, directional_accuracy, directional_accuracy_std,
                     signal_count_total, win_count, loss_count,
                     avg_return_pct, avg_win_pct, avg_loss_pct, profit_factor,
                     is_simulated, data_quality_warning)
                VALUES (?,?,?,?, ?,?,?, ?,?,?, ?,?,?, ?,?,?,?, ?,?)
            """
        for r in results:
            params = [
                r['symbol'], r['agent_name'], str(run_date), r['methodology'],
                r['train_window_days'], r['test_window_days'], r['step_size_days'],
                r['windows_tested'], r['directional_accuracy'], r['directional_accuracy_std'],
                r['signal_count_total'], r['win_count'], r['loss_count'],
                r['avg_return_pct'], r['avg_win_pct'], r['avg_loss_pct'], r['profit_factor'],
                r['is_simulated'], r['data_quality_warning'],
            ]
            _execute(self.conn, upsert, params)

    # ── 7. Aggregate summary ─────────────────────────────────
    def compute_aggregate_summary(self, results: list, run_date: date) -> dict:
        if not results:
            return {
                'run_date': str(run_date), 'symbols_tested': 0, 'symbols_skipped': 0,
                'total_agent_results': 0, 'avg_directional_accuracy': 0,
                'best_symbol': None, 'best_symbol_accuracy': 0,
                'worst_symbol': None, 'worst_symbol_accuracy': 0,
                'best_agent': None, 'best_agent_accuracy': 0,
                'methodology': 'walk_forward',
                'train_window_days': self.cfg['train_window_days'],
                'test_window_days':  self.cfg['test_window_days'],
                'windows_per_symbol': 0,
            }

        all_accs = [r['directional_accuracy'] for r in results]
        avg_acc  = float(np.mean(all_accs))

        # Best/worst by consensus agent
        consensus_results = [r for r in results if r['agent_name'] == 'consensus']
        best_sym  = max(consensus_results, key=lambda x: x['directional_accuracy'], default=None)
        worst_sym = min(consensus_results, key=lambda x: x['directional_accuracy'], default=None)

        # Best agent (avg across all symbols)
        agent_accs = {}
        for r in results:
            agent_accs.setdefault(r['agent_name'], []).append(r['directional_accuracy'])
        best_agent = max(agent_accs, key=lambda a: np.mean(agent_accs[a]), default=None)

        symbols_tested = len(set(r['symbol'] for r in results))
        avg_windows = int(np.mean([r['windows_tested'] for r in results])) if results else 0

        return {
            'run_date':                  str(run_date),
            'symbols_tested':            symbols_tested,
            'symbols_skipped':           0,  # updated in run_full_backtest
            'total_agent_results':       len(results),
            'avg_directional_accuracy':  round(avg_acc, 4),
            'best_symbol':               best_sym['symbol']  if best_sym  else None,
            'best_symbol_accuracy':      best_sym['directional_accuracy']  if best_sym  else 0,
            'worst_symbol':              worst_sym['symbol'] if worst_sym else None,
            'worst_symbol_accuracy':     worst_sym['directional_accuracy'] if worst_sym else 0,
            'best_agent':                best_agent,
            'best_agent_accuracy':       round(float(np.mean(agent_accs[best_agent])), 4) if best_agent else 0,
            'methodology':               'walk_forward',
            'train_window_days':         self.cfg['train_window_days'],
            'test_window_days':          self.cfg['test_window_days'],
            'windows_per_symbol':        avg_windows,
        }

    # ── 8. Save run log ──────────────────────────────────────
    def save_run_log(self, run_date: date, attempted: int, total_results: int,
                     errors: list, summary: dict, duration: float = 0):
        errors_json = json.dumps(errors)
        if self._pg:
            sql = """
                INSERT INTO backtest_run_log
                    (run_date, symbols_attempted, symbols_completed, symbols_skipped,
                     symbols_failed, total_results, avg_directional_accuracy,
                     best_symbol, best_agent, run_duration_seconds, errors_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_date) DO UPDATE SET
                    symbols_completed        = EXCLUDED.symbols_completed,
                    symbols_failed           = EXCLUDED.symbols_failed,
                    total_results            = EXCLUDED.total_results,
                    avg_directional_accuracy = EXCLUDED.avg_directional_accuracy,
                    best_symbol              = EXCLUDED.best_symbol,
                    best_agent               = EXCLUDED.best_agent,
                    run_duration_seconds     = EXCLUDED.run_duration_seconds,
                    errors_json              = EXCLUDED.errors_json
            """
        else:
            sql = """
                INSERT OR REPLACE INTO backtest_run_log
                    (run_date, symbols_attempted, symbols_completed, symbols_skipped,
                     symbols_failed, total_results, avg_directional_accuracy,
                     best_symbol, best_agent, run_duration_seconds, errors_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """
        completed = attempted - len(errors)
        skipped   = summary.get('symbols_skipped', 0)
        _execute(self.conn, sql, [
            str(run_date), attempted, completed, skipped,
            len(errors), total_results,
            summary.get('avg_directional_accuracy', 0),
            summary.get('best_symbol'),
            summary.get('best_agent'),
            duration,
            errors_json,
        ])

    # ── 9. Full backtest run ─────────────────────────────────
    def run_full_backtest(self) -> dict:
        import time
        run_date   = date.today()
        start_time = time.time()
        symbols    = self.get_symbols_to_test()
        logger.info(f"[WFB] Starting walk-forward backtest for {len(symbols)} symbols")

        all_results, errors, skipped = [], [], 0

        for symbol in symbols:
            try:
                sym_results = self.run_walk_forward_for_symbol(symbol)
                all_results.extend(sym_results)
                self.save_results(sym_results, run_date)
                logger.info(f"[WFB] {symbol}: {len(sym_results)} agent results saved")
            except InsufficientDataError as e:
                skipped += 1
                logger.warning(f"[WFB] {symbol}: skipped — {e}")
            except Exception as e:
                errors.append({'symbol': symbol, 'error': str(e)})
                logger.error(f"[WFB] {symbol}: failed — {e}", exc_info=True)

        duration = round(time.time() - start_time, 1)
        summary  = self.compute_aggregate_summary(all_results, run_date)
        summary['symbols_skipped'] = skipped
        self.save_run_log(run_date, len(symbols), len(all_results), errors, summary, duration)

        logger.info(f"[WFB] Complete: {summary['symbols_tested']} symbols, "
                    f"avg accuracy {summary['avg_directional_accuracy']:.1%}, "
                    f"{len(errors)} errors, {duration}s")
        return summary
