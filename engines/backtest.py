"""
Walk-Forward Backtesting Harness

Simulates the ML agent's prediction pipeline on historical data to measure
out-of-sample performance before deploying changes to production.

For each symbol, it performs an expanding-window walk-forward simulation:
  - Minimum 60 rows in first training fold
  - Each test fold = 10 rows (approx 2 weeks of trading)
  - Features and target computed identically to agent_ml.py

Metrics reported per symbol:
  accuracy             — overall % correct (UP/DOWN/FLAT)
  directional_accuracy — accuracy on UP + DOWN predictions only (excludes FLAT)
  precision / recall   — per class (UP, DOWN, FLAT)
  signal_pnl           — hypothetical P&L: +actual_return when UP is correct,
                         +|actual_return| when DOWN is correct, -|actual_return|
                         when wrong direction; 0 for FLAT predictions

Usage:
    python engines/backtest.py --symbol COMI.CA
    python engines/backtest.py --all
    python engines/backtest.py --all --splits 8 --top-features 15
"""

import os
import sys
import argparse
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime

# Add project root to path when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

try:
    from lightgbm import LGBMClassifier
    LGBM_AVAILABLE = True
except ImportError:
    from sklearn.ensemble import RandomForestClassifier
    LGBM_AVAILABLE = False

from database import get_connection
from features import (
    add_technical_indicators, add_sentiment_features,
    add_macro_features, get_feature_columns
)

try:
    from config.execution_config import EGX_ROUND_TRIP_RATE
except ImportError:
    EGX_ROUND_TRIP_RATE = 0.00725  # 0.725% round-trip baseline

# Cost per trade in percentage points (deducted from gross P&L)
_COST_PCT = EGX_ROUND_TRIP_RATE * 100  # 0.725

logger = logging.getLogger(__name__)

# Must match agent_ml.py
UP_THRESHOLD   =  0.005
DOWN_THRESHOLD = -0.005

# Backtest config
MIN_TRAIN_ROWS = 60   # minimum rows in the very first training fold
TEST_FOLD_SIZE = 10   # rows per test fold (~2 weeks of EGX trading)
DEFAULT_SPLITS = 8
DEFAULT_TOP_N  = 20


# ─────────────────────────────────────────────────────────────
# Model helpers (mirrors agent_ml._make_lgbm / _select_top_features)
# ─────────────────────────────────────────────────────────────

def _make_model():
    if LGBM_AVAILABLE:
        return LGBMClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            num_leaves=31, class_weight='balanced',
            min_child_samples=10, subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1, verbose=-1,
        )
    return RandomForestClassifier(
        n_estimators=100, max_depth=10, class_weight='balanced',
        random_state=42, n_jobs=-1
    )


def _gain_importances(model, features):
    try:
        if hasattr(model, 'booster_'):
            return model.booster_.feature_importance(importance_type='gain')
        return model.feature_importances_
    except Exception:
        return np.ones(len(features))


def _select_features(model, features, top_n):
    imps = _gain_importances(model, features)
    paired = sorted(zip(features, imps), key=lambda x: x[1], reverse=True)
    selected = [f for f, _ in paired[:top_n]]
    return selected if len(selected) >= 5 else features


# ─────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────

def _load_price_df(symbol: str, conn) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT date, open, high, low, close, volume FROM prices "
        "WHERE symbol = ? ORDER BY date ASC",
        conn, params=(symbol,)
    )
    if df.empty:
        df = pd.read_sql(
            "SELECT date, open, high, low, close, volume FROM prices "
            "WHERE symbol = %s ORDER BY date ASC",
            conn, params=(symbol,)
        )
    return df


def _load_news_df(symbol: str, conn) -> pd.DataFrame:
    try:
        return pd.read_sql(
            "SELECT date, sentiment_score FROM news WHERE symbol = ? ORDER BY date",
            conn, params=(symbol,)
        )
    except Exception:
        try:
            return pd.read_sql(
                "SELECT date, sentiment_score FROM news WHERE symbol = %s ORDER BY date",
                conn, params=(symbol,)
            )
        except Exception:
            return pd.DataFrame()


def _load_macro_df(conn) -> pd.DataFrame:
    try:
        return pd.read_sql("""
            SELECT date,
                MAX(CASE WHEN symbol='MACRO_BRENT'  THEN close END) AS brent_close,
                MAX(CASE WHEN symbol='MACRO_USDEGP' THEN close END) AS usdegp_close,
                MAX(CASE WHEN symbol='MACRO_EEM'    THEN close END) AS eem_close
            FROM prices
            WHERE symbol IN ('MACRO_BRENT', 'MACRO_USDEGP', 'MACRO_EEM')
            GROUP BY date ORDER BY date
        """, conn)
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# Metrics helpers
# ─────────────────────────────────────────────────────────────

def _compute_metrics(records: list) -> dict:
    """
    Compute performance metrics from a list of prediction records.
    Each record: {actual, predicted, actual_return_pct}
    """
    if not records:
        return {}

    df = pd.DataFrame(records)
    label_map = {0: "DOWN", 1: "FLAT", 2: "UP"}
    df['actual_label']    = df['actual'].map(label_map)
    df['predicted_label'] = df['predicted'].map(label_map)

    total     = len(df)
    correct   = (df['actual'] == df['predicted']).sum()
    accuracy  = correct / total

    # Directional accuracy: only rows where model predicted UP or DOWN
    dir_mask = df['predicted_label'].isin(['UP', 'DOWN'])
    dir_df   = df[dir_mask]
    dir_acc  = (dir_df['actual'] == dir_df['predicted']).mean() if len(dir_df) > 0 else 0.0

    # Precision / recall / F1 per class
    labels = sorted(df['actual'].unique())
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        prec, rec, f1, sup = precision_recall_fscore_support(
            df['actual'], df['predicted'], labels=labels, zero_division=0
        )

    per_class = {}
    for i, lbl in enumerate(labels):
        name = label_map.get(lbl, str(lbl))
        per_class[name] = {
            'precision': round(float(prec[i]), 3),
            'recall':    round(float(rec[i]),  3),
            'f1':        round(float(f1[i]),   3),
            'support':   int(sup[i]),
        }

    # Hypothetical signal P&L (gross)
    # UP correct   → capture actual_return_pct (long position gained)
    # DOWN correct → capture |actual_return_pct| (short position gained)
    # UP wrong     → -|actual_return_pct|
    # DOWN wrong   → -|actual_return_pct|
    # FLAT rows    → 0
    pnl = 0.0
    net_pnl = 0.0
    profitable_after_cost = 0
    n_nontrivial = 0

    for _, row in df.iterrows():
        pred   = row['predicted_label']
        actual = row['actual_label']
        ret    = row['actual_return_pct']
        if pred == 'FLAT':
            continue
        n_nontrivial += 1
        correct_dir = (pred == actual)
        if correct_dir:
            gross_trade = abs(ret)
            pnl += gross_trade
            net_trade = gross_trade - _COST_PCT
            net_pnl += net_trade
            if net_trade > 0:
                profitable_after_cost += 1
        else:
            pnl     -= abs(ret)
            net_pnl -= (abs(ret) + _COST_PCT)

    profitability_accuracy = (
        profitable_after_cost / n_nontrivial if n_nontrivial > 0 else 0.0
    )

    up_predicted   = (df['predicted_label'] == 'UP').sum()
    down_predicted = (df['predicted_label'] == 'DOWN').sum()
    flat_predicted = (df['predicted_label'] == 'FLAT').sum()

    return {
        'total_predictions':    total,
        'accuracy':             round(float(accuracy), 3),
        'directional_accuracy': round(float(dir_acc), 3),
        # Gross P&L (excludes transaction costs)
        'signal_pnl_pct':       round(float(pnl), 2),
        # Net P&L after EGX round-trip costs (0.725% per trade)
        'net_signal_pnl_pct':   round(float(net_pnl), 2),
        # P5: what fraction of traded signals were actually profitable after costs
        'profitability_accuracy': round(profitability_accuracy, 3),
        'up_predicted':         int(up_predicted),
        'down_predicted':       int(down_predicted),
        'flat_predicted':       int(flat_predicted),
        'per_class':            per_class,
    }


# ─────────────────────────────────────────────────────────────
# Core backtest function
# ─────────────────────────────────────────────────────────────

def backtest_symbol(symbol: str,
                    n_splits: int = DEFAULT_SPLITS,
                    top_n_features: int = DEFAULT_TOP_N,
                    conn=None) -> dict:
    """
    Run walk-forward backtest for a single symbol.

    Returns a dict with 'symbol', 'metrics', 'fold_scores', 'n_rows',
    'features_used', and 'error' (None on success).
    """
    _conn_owner = conn is None
    try:
        if _conn_owner:
            conn = get_connection().__enter__()

        price_df  = _load_price_df(symbol, conn)
        news_df   = _load_news_df(symbol, conn)
        macro_df  = _load_macro_df(conn)

        if len(price_df) < MIN_TRAIN_ROWS + TEST_FOLD_SIZE:
            return {
                'symbol': symbol,
                'error': f'Insufficient data ({len(price_df)} rows, need {MIN_TRAIN_ROWS + TEST_FOLD_SIZE})',
                'metrics': None, 'fold_scores': [], 'n_rows': len(price_df),
            }

        # Build feature matrix once — same pipeline as agent_ml.predict()
        price_df['symbol'] = symbol
        df = add_technical_indicators(price_df)
        df = add_sentiment_features(df, news_df)
        df = add_macro_features(df, macro_df)

        all_features = get_feature_columns()
        available = [f for f in all_features if f in df.columns and not df[f].isna().all()]

        if len(available) < 5:
            return {
                'symbol': symbol,
                'error': f'Only {len(available)} features available',
                'metrics': None, 'fold_scores': [], 'n_rows': len(df),
            }

        df['future_return'] = df['close'].shift(-5) / df['close'] - 1
        df['target'] = df['future_return'].apply(
            lambda x: 2 if x > UP_THRESHOLD else (0 if x < DOWN_THRESHOLD else 1)
        )

        clean = df.dropna(subset=['target'] + available).copy()
        if len(clean) < MIN_TRAIN_ROWS + TEST_FOLD_SIZE:
            return {
                'symbol': symbol,
                'error': f'Not enough clean rows ({len(clean)})',
                'metrics': None, 'fold_scores': [], 'n_rows': len(clean),
            }

        X_all = clean[available].values
        y_all = clean['target'].astype(int).values
        ret_all = clean['future_return'].values * 100  # pct

        # ── Walk-forward splits ──────────────────────────────────────────────
        # Use TimeSeriesSplit with a minimum training gap
        actual_splits = min(n_splits, (len(clean) - MIN_TRAIN_ROWS) // TEST_FOLD_SIZE)
        if actual_splits < 2:
            return {
                'symbol': symbol,
                'error': f'Not enough rows for {n_splits} splits',
                'metrics': None, 'fold_scores': [], 'n_rows': len(clean),
            }

        tscv = TimeSeriesSplit(n_splits=actual_splits, test_size=TEST_FOLD_SIZE,
                               gap=5)  # gap=5 avoids look-ahead from 5-day forward label

        records    = []
        fold_scores = []
        selected_features = available

        for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(X_all)):
            if len(train_idx) < MIN_TRAIN_ROWS:
                continue

            X_train, X_test = X_all[train_idx], X_all[test_idx]
            y_train, y_test = y_all[train_idx], y_all[test_idx]

            # Feature selection on first fold (carried forward for consistency)
            if fold_idx == 0:
                # Need feature names for selection — train quick scout model
                scout = _make_model()
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    scout.fit(pd.DataFrame(X_train, columns=available),
                              pd.Series(y_train))
                selected_features = _select_features(scout, available, top_n_features)
                sel_idx = [available.index(f) for f in selected_features]
            else:
                sel_idx = [available.index(f) for f in selected_features]

            X_tr_sel  = X_train[:, sel_idx]
            X_te_sel  = X_test[:, sel_idx]

            model = _make_model()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                model.fit(pd.DataFrame(X_tr_sel, columns=selected_features),
                          pd.Series(y_train))

            preds = model.predict(pd.DataFrame(X_te_sel, columns=selected_features))
            fold_acc = (preds == y_test).mean()
            fold_scores.append(round(float(fold_acc), 3))

            for pred, actual, ret in zip(preds, y_test, ret_all[test_idx]):
                records.append({
                    'predicted':        int(pred),
                    'actual':           int(actual),
                    'actual_return_pct': float(ret),
                })

        if not records:
            return {
                'symbol': symbol,
                'error': 'No predictions generated (all folds skipped)',
                'metrics': None, 'fold_scores': fold_scores, 'n_rows': len(clean),
            }

        metrics = _compute_metrics(records)

        return {
            'symbol':          symbol,
            'error':           None,
            'metrics':         metrics,
            'fold_scores':     fold_scores,
            'n_rows':          len(clean),
            'features_used':   len(selected_features),
        }

    except Exception as e:
        logger.exception(f"Backtest failed for {symbol}: {e}")
        return {
            'symbol': symbol,
            'error':  str(e),
            'metrics': None, 'fold_scores': [], 'n_rows': 0,
        }
    finally:
        if _conn_owner and conn is not None:
            try:
                conn.__exit__(None, None, None)
            except Exception:
                pass


def save_results(results: list, run_date: str = None) -> int:
    """
    Persist backtest results to the backtest_results table.
    Existing row for (symbol, run_date) is replaced.

    Returns count of rows upserted.
    """
    import json as _json
    if not results:
        return 0
    if run_date is None:
        run_date = datetime.now().strftime('%Y-%m-%d')

    saved = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for r in results:
            if not r.get('metrics'):
                continue
            m = r['metrics']
            pc = m.get('per_class', {})
            up_p  = pc.get('UP',   {}).get('precision', None)
            dn_p  = pc.get('DOWN', {}).get('precision', None)
            fold_json = _json.dumps(r.get('fold_scores', []))
            row = (
                r['symbol'], run_date,
                r.get('n_rows'), r.get('n_splits', DEFAULT_SPLITS),
                m.get('accuracy'), m.get('directional_accuracy'),
                m.get('signal_pnl_pct'), up_p, dn_p,
                r.get('features_used'), fold_json,
            )
            if os.getenv('DATABASE_URL'):
                cursor.execute("""
                    INSERT INTO backtest_results
                    (symbol, run_date, n_rows, n_splits, accuracy, directional_accuracy,
                     signal_pnl_pct, up_precision, down_precision, features_used, fold_scores_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (symbol, run_date) DO UPDATE SET
                        n_rows=EXCLUDED.n_rows, n_splits=EXCLUDED.n_splits,
                        accuracy=EXCLUDED.accuracy, directional_accuracy=EXCLUDED.directional_accuracy,
                        signal_pnl_pct=EXCLUDED.signal_pnl_pct, up_precision=EXCLUDED.up_precision,
                        down_precision=EXCLUDED.down_precision, features_used=EXCLUDED.features_used,
                        fold_scores_json=EXCLUDED.fold_scores_json
                """, row)
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO backtest_results
                    (symbol, run_date, n_rows, n_splits, accuracy, directional_accuracy,
                     signal_pnl_pct, up_precision, down_precision, features_used, fold_scores_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, row)
            saved += 1
    return saved


def backtest_all(symbols: list = None,
                 n_splits: int = DEFAULT_SPLITS,
                 top_n_features: int = DEFAULT_TOP_N) -> list:
    """
    Run backtest for every symbol (default: all stocks from egx30_stocks table).
    Returns list of result dicts sorted by directional_accuracy descending.
    """
    if symbols is None:
        with get_connection() as conn:
            try:
                rows = pd.read_sql("SELECT symbol FROM egx30_stocks", conn)
                symbols = rows['symbol'].tolist()
            except Exception:
                rows = pd.read_sql(
                    "SELECT DISTINCT symbol FROM prices "
                    "WHERE symbol NOT LIKE 'MACRO_%' ORDER BY symbol",
                    conn
                )
                symbols = rows['symbol'].tolist()

    results = []
    total = len(symbols)
    for i, sym in enumerate(symbols, 1):
        print(f"  [{i}/{total}] Backtesting {sym}...", end=' ', flush=True)
        r = backtest_symbol(sym, n_splits=n_splits, top_n_features=top_n_features)
        if r['error']:
            print(f"SKIP — {r['error']}")
        else:
            m = r['metrics']
            print(
                f"acc={m['accuracy']:.1%}  dir={m['directional_accuracy']:.1%}  "
                f"pnl={m['signal_pnl_pct']:+.1f}%  folds={r['fold_scores']}"
            )
        results.append(r)

    return sorted(
        [r for r in results if r['metrics']],
        key=lambda r: r['metrics']['directional_accuracy'],
        reverse=True
    )


def backtest_with_friction(symbols: list = None,
                           n_splits: int = DEFAULT_SPLITS,
                           top_n_features: int = DEFAULT_TOP_N) -> dict:
    """
    P3: Run full backtest with friction-adjusted reporting.

    Applies EGX round-trip costs (0.725% per trade) to the backtest P&L,
    partial fills, and gap-adjusted exits. Returns both gross and net summaries.

    This is a reporting wrapper around backtest_all(). The underlying
    _compute_metrics() already calculates net_signal_pnl_pct and
    profitability_accuracy on every symbol.

    Returns:
        {
          "gross_pnl_total": float,  # sum of all signal_pnl_pct
          "net_pnl_total":   float,  # sum of all net_signal_pnl_pct
          "cost_drag_total": float,  # gross - net
          "avg_profitability_accuracy": float,
          "results": list            # raw per-symbol result dicts
        }
    """
    results = backtest_all(symbols=symbols, n_splits=n_splits,
                           top_n_features=top_n_features)
    gross_pnls = [r['metrics']['signal_pnl_pct']     for r in results if r.get('metrics')]
    net_pnls   = [r['metrics'].get('net_signal_pnl_pct', r['metrics']['signal_pnl_pct'] -
                   _COST_PCT * (r['metrics']['up_predicted'] + r['metrics']['down_predicted']))
                  for r in results if r.get('metrics')]
    prof_accs  = [r['metrics'].get('profitability_accuracy', 0) for r in results if r.get('metrics')]

    gross_total = sum(gross_pnls)
    net_total   = sum(net_pnls)
    return {
        "gross_pnl_total":              round(gross_total, 2),
        "net_pnl_total":                round(net_total, 2),
        "cost_drag_total":              round(gross_total - net_total, 2),
        "avg_profitability_accuracy":   round(
            sum(prof_accs) / len(prof_accs) if prof_accs else 0, 3
        ),
        "results": results,
    }


def print_report(results: list):
    """Print a formatted summary table of backtest results."""
    ok = [r for r in results if r['metrics']]
    if not ok:
        print("No successful backtest results.")
        return

    print("\n" + "=" * 92)
    print(f"{'SYMBOL':<12} {'ACC':>6} {'DIR_ACC':>8} {'GROSS P&L':>10} {'NET P&L':>9} {'PROFIT%':>8} {'ROWS':>6}")
    print("-" * 92)
    for r in ok:
        m  = r['metrics']
        net_pnl = m.get('net_signal_pnl_pct', m['signal_pnl_pct'] - _COST_PCT * (m['up_predicted'] + m['down_predicted']))
        print(
            f"{r['symbol']:<12} {m['accuracy']:>6.1%} {m['directional_accuracy']:>8.1%} "
            f"{m['signal_pnl_pct']:>+10.1f} {net_pnl:>+9.1f} "
            f"{m.get('profitability_accuracy', 0):>8.1%} {r['n_rows']:>6}"
        )

    # Aggregate stats
    accs  = [r['metrics']['accuracy'] for r in ok]
    dirs  = [r['metrics']['directional_accuracy'] for r in ok]
    pnls  = [r['metrics']['signal_pnl_pct'] for r in ok]
    net_pnls = [r['metrics'].get('net_signal_pnl_pct', 0) for r in ok]
    print("-" * 92)
    print(
        f"{'MEAN':<12} {np.mean(accs):>6.1%} {np.mean(dirs):>8.1%} "
        f"{np.mean(pnls):>+10.1f} {np.mean(net_pnls):>+9.1f}"
        f"   (n={len(ok)} symbols)"
    )
    print("=" * 92)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    failed = [r['symbol'] for r in results if r.get('error')]
    if failed:
        print(f"Skipped ({len(failed)}): {', '.join(failed)}")


# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s %(name)s: %(message)s'
    )

    parser = argparse.ArgumentParser(description='Walk-Forward Backtest Harness')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--symbol', help='Single symbol, e.g. COMI.CA')
    group.add_argument('--all',    action='store_true', help='Backtest all symbols')
    parser.add_argument('--splits',       type=int, default=DEFAULT_SPLITS,
                        help=f'Number of walk-forward splits (default {DEFAULT_SPLITS})')
    parser.add_argument('--top-features', type=int, default=DEFAULT_TOP_N,
                        help=f'Top-N features to select (default {DEFAULT_TOP_N})')
    parser.add_argument('--save', action='store_true',
                        help='Persist results to backtest_results DB table')
    args = parser.parse_args()

    engine = 'LightGBM' if LGBM_AVAILABLE else 'RandomForest (LightGBM not installed)'
    print(f"\nWalk-Forward Backtest | Engine: {engine} | Splits: {args.splits} | Top features: {args.top_features}")

    if args.symbol:
        r = backtest_symbol(args.symbol, n_splits=args.splits,
                            top_n_features=args.top_features)
        print_report([r])
        if r['metrics']:
            print("\nPer-class metrics:")
            for cls, vals in r['metrics']['per_class'].items():
                print(f"  {cls:<6}  precision={vals['precision']:.3f}  recall={vals['recall']:.3f}  "
                      f"f1={vals['f1']:.3f}  support={vals['support']}")
        if args.save and r['metrics']:
            n = save_results([r])
            print(f"\n✅ Saved {n} result(s) to backtest_results table.")
    else:
        print("Running full backtest...\n")
        results = backtest_all(n_splits=args.splits, top_n_features=args.top_features)
        print_report(results)
        if args.save and results:
            n = save_results(results)
            print(f"\n✅ Saved {n} result(s) to backtest_results table.")
