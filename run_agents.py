"""
Main Agent Execution Script — 3-Layer Consensus Pipeline.

Flow:
  1. Fetch price data + sentiment for each stock
  2. Run 4 signal agents → structured AgentSignal dicts (Layer 1)
  3. Run Consensus Engine (Bull/Bear + Risk gating) (Layers 2 & 3)
  4. Store individual predictions + consensus results to database
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
import config
from database import get_connection
from sentiment_gemini import get_latest_sentiment
import sys
import traceback
import logging

logger = logging.getLogger(__name__)

# Import agents
try:
    from agents.agent_rsi import RSIAgent
    from agents.agent_ma import MAAgent
    from agents.agent_volume import VolumeAgent
    from agents.agent_ml import MLAgent
    from agents.consensus_engine import run_consensus
    print("✅ All agents imported successfully (including Consensus Engine)")
except Exception as e:
    print(f"❌ Failed to import agents: {e}")
    traceback.print_exc()
    sys.exit(1)

# Import Gemini LLM agent (optional — gracefully skipped if unavailable)
try:
    from agents.gemini_agent import GeminiAgent
    _gemini_agent = GeminiAgent()
    if _gemini_agent._enabled:
        print("✅ Gemini LLM Agent loaded and enabled")
    else:
        print("⚠️  Gemini LLM Agent loaded but disabled (GOOGLE_API_KEY not set)")
except Exception as e:
    _gemini_agent = None
    print(f"⚠️  Gemini LLM Agent not available: {e}")


def _compute_market_data(df):
    """
    Derive market-level metrics from price DataFrame for the Risk Agent.
    Returns dict with volume_20d_avg, volatility_20d, price, drawdowns, 52w range.
    """
    if df is None or len(df) < 5:
        return None

    market = {}
    market['price'] = float(df['close'].iloc[-1])

    # 20-day average volume
    if 'volume' in df.columns and len(df) >= 20:
        market['volume_20d_avg'] = float(df['volume'].tail(20).mean())
    else:
        market['volume_20d_avg'] = float(df['volume'].mean()) if 'volume' in df.columns else None

    # 20-day daily volatility (std of log returns)
    if len(df) >= 21:
        returns = df['close'].pct_change().dropna().tail(20)
        market['volatility_20d'] = float(returns.std()) if len(returns) > 0 else None
    else:
        market['volatility_20d'] = None

    # 5-day drawdown
    if len(df) >= 6:
        price_5d_ago = float(df['close'].iloc[-6])
        market['drawdown_5d'] = (market['price'] - price_5d_ago) / price_5d_ago if price_5d_ago > 0 else 0
    else:
        market['drawdown_5d'] = 0

    # 20-day drawdown
    if len(df) >= 21:
        price_20d_ago = float(df['close'].iloc[-21])
        market['drawdown_20d'] = (market['price'] - price_20d_ago) / price_20d_ago if price_20d_ago > 0 else 0
    else:
        market['drawdown_20d'] = 0

    # 52-week range position
    if len(df) >= 252:
        low_52w = float(df['close'].tail(252).min())
        high_52w = float(df['close'].tail(252).max())
    else:
        low_52w = float(df['close'].min())
        high_52w = float(df['close'].max())

    if high_52w > low_52w:
        market['range_52w_position'] = (market['price'] - low_52w) / (high_52w - low_52w)
    else:
        market['range_52w_position'] = 0.5

    return market


def _store_consensus(conn, stock, today, consensus_result):
    """Store consensus result in consensus_results table."""
    cursor = conn.cursor()

    # Serialize JSON fields
    bull_json = json.dumps(consensus_result.get('bull_case', {}))
    bear_json = json.dumps(consensus_result.get('bear_case', {}))
    risk_json = json.dumps(consensus_result.get('risk_assessment', {}))
    signals_json = json.dumps(consensus_result.get('agent_signals', []))
    chain_json = json.dumps(consensus_result.get('reasoning_chain', []))
    display_json = json.dumps(consensus_result.get('display', {}))

    if os.getenv('DATABASE_URL'):
        cursor.execute("""
            INSERT INTO consensus_results
            (symbol, prediction_date, final_signal, conviction, confidence,
             risk_adjusted, agent_agreement, agents_agreeing, agents_total,
             majority_direction, bull_score, bear_score, risk_action, risk_score,
             bull_case_json, bear_case_json, risk_assessment_json,
             agent_signals_json, reasoning_chain_json, display_json)
            VALUES (%s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s)
            ON CONFLICT (symbol, prediction_date)
            DO UPDATE SET
                final_signal = EXCLUDED.final_signal,
                conviction = EXCLUDED.conviction,
                confidence = EXCLUDED.confidence,
                risk_adjusted = EXCLUDED.risk_adjusted,
                agent_agreement = EXCLUDED.agent_agreement,
                agents_agreeing = EXCLUDED.agents_agreeing,
                agents_total = EXCLUDED.agents_total,
                majority_direction = EXCLUDED.majority_direction,
                bull_score = EXCLUDED.bull_score,
                bear_score = EXCLUDED.bear_score,
                risk_action = EXCLUDED.risk_action,
                risk_score = EXCLUDED.risk_score,
                bull_case_json = EXCLUDED.bull_case_json,
                bear_case_json = EXCLUDED.bear_case_json,
                risk_assessment_json = EXCLUDED.risk_assessment_json,
                agent_signals_json = EXCLUDED.agent_signals_json,
                reasoning_chain_json = EXCLUDED.reasoning_chain_json,
                display_json = EXCLUDED.display_json
        """, (
            stock, today,
            consensus_result.get('final_signal', 'HOLD'),
            consensus_result.get('conviction', 'LOW'),
            consensus_result.get('confidence', 0),
            consensus_result.get('risk_adjusted', False),
            consensus_result.get('agent_agreement', 0),
            consensus_result.get('agents_agreeing', 0),
            consensus_result.get('agents_total', 0),
            consensus_result.get('majority_direction', 'HOLD'),
            consensus_result.get('bull_score', 0),
            consensus_result.get('bear_score', 0),
            consensus_result.get('risk_action', 'PASS'),
            consensus_result.get('risk_score', 0),
            bull_json, bear_json, risk_json,
            signals_json, chain_json, display_json
        ))
    else:
        cursor.execute("""
            INSERT OR REPLACE INTO consensus_results
            (symbol, prediction_date, final_signal, conviction, confidence,
             risk_adjusted, agent_agreement, agents_agreeing, agents_total,
             majority_direction, bull_score, bear_score, risk_action, risk_score,
             bull_case_json, bear_case_json, risk_assessment_json,
             agent_signals_json, reasoning_chain_json, display_json)
            VALUES (?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?)
        """, (
            stock, today,
            consensus_result.get('final_signal', 'HOLD'),
            consensus_result.get('conviction', 'LOW'),
            consensus_result.get('confidence', 0),
            1 if consensus_result.get('risk_adjusted', False) else 0,
            consensus_result.get('agent_agreement', 0),
            consensus_result.get('agents_agreeing', 0),
            consensus_result.get('agents_total', 0),
            consensus_result.get('majority_direction', 'HOLD'),
            consensus_result.get('bull_score', 0),
            consensus_result.get('bear_score', 0),
            consensus_result.get('risk_action', 'PASS'),
            consensus_result.get('risk_score', 0),
            bull_json, bear_json, risk_json,
            signals_json, chain_json, display_json
        ))


def execute():
    """
    Run the full 3-layer prediction pipeline for all configured stocks.

    Workflow:
    1. Initialize signal agents (RSI, MA, Volume, ML).
    2. For each stock:
       a. Load price history + sentiment
       b. Run all 4 agents → structured AgentSignal dicts
       c. Run Consensus Engine (Bull/Bear + Risk gating)
       d. Store predictions + consensus results
    """
    try:
        print("🚀 Starting 3-Layer Prediction Pipeline...")

        # Create signal agents
        rsi_agent = RSIAgent()
        ma_agent = MAAgent(short_window=config.MA_SHORT_PERIOD, long_window=config.MA_LONG_PERIOD)
        vol_agent = VolumeAgent()
        ml_agent = MLAgent()

        agents = [rsi_agent, ma_agent, vol_agent, ml_agent]
        gemini_agent = _gemini_agent  # module-level instance (None if unavailable)
        print(f"✅ Created {len(agents)} technical agents" +
              (" + Gemini LLM Agent" if gemini_agent and gemini_agent._enabled else ""))

        # Define prediction windows
        today = datetime.now().strftime('%Y-%m-%d')
        target = (datetime.now() + timedelta(days=config.PREDICTION_HORIZON_DAYS)).strftime('%Y-%m-%d')
        print(f"📅 Prediction date: {today}")
        print(f"🎯 Target date: {target}")
        print(f"📊 Processing {len(config.ALL_STOCKS)} stocks...")

        # Portfolio-level tracking for risk concentration checks
        portfolio_signals = []
        risk_cfg = getattr(config, 'RISK_CONFIG', None)

        with get_connection() as conn:
            cursor = conn.cursor()

            for stock in config.ALL_STOCKS:
                print(f"\n{'='*50}")
                print(f"  📈 {stock}")
                print(f"{'='*50}")

                # ── Fetch price data ──
                if os.getenv('DATABASE_URL'):
                    cursor.execute(
                        "SELECT date, open, high, low, close, volume FROM prices WHERE symbol=%s ORDER BY date",
                        (stock,)
                    )
                else:
                    cursor.execute(
                        "SELECT date, open, high, low, close, volume FROM prices WHERE symbol=? ORDER BY date",
                        (stock,)
                    )

                rows = cursor.fetchall()
                if os.getenv('DATABASE_URL'):
                    df = pd.DataFrame(rows)
                else:
                    df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

                print(f"  📊 Loaded {len(df)} price records")

                if len(df) < 50:
                    print(f"  ⚠️  Not enough data ({len(df)} rows), skipping")
                    continue

                # Add symbol column for ML agent
                df['symbol'] = stock

                # ── Fetch sentiment ──
                sentiment = get_latest_sentiment(stock)
                if sentiment:
                    print(f"  💬 Sentiment: {sentiment.get('sentiment_label', 'N/A')} ({sentiment.get('avg_sentiment', 0):.2f})")
                else:
                    print(f"  💬 Sentiment: No data")

                # ── Layer 1: Run signal agents → structured output ──
                agent_signals = []
                cursor = conn.cursor()

                for agent in agents:
                    try:
                        # Use new predict_signal() for structured output
                        signal_dict = agent.predict_signal(df, symbol=stock, sentiment=sentiment)
                        agent_signals.append(signal_dict)

                        prediction = signal_dict.get('prediction', 'HOLD')
                        confidence = signal_dict.get('confidence', 0)
                        reasoning_json = json.dumps(signal_dict.get('reasoning', {}))

                        # Store individual prediction
                        if os.getenv('DATABASE_URL'):
                            cursor.execute("""
                                INSERT INTO predictions
                                (symbol, prediction_date, target_date, agent_name, prediction, confidence, reasoning)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (symbol, prediction_date, target_date, agent_name)
                                DO UPDATE SET prediction = EXCLUDED.prediction,
                                             confidence = EXCLUDED.confidence,
                                             reasoning = EXCLUDED.reasoning
                            """, (stock, today, target, agent.name, prediction, confidence, reasoning_json))
                        else:
                            cursor.execute("""
                                INSERT OR REPLACE INTO predictions
                                (symbol, prediction_date, target_date, agent_name, prediction, confidence, reasoning)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (stock, today, target, agent.name, prediction, confidence, reasoning_json))

                        print(f"  🔮 {agent.name}: {prediction} ({confidence:.0f}%)")

                    except Exception as e:
                        print(f"  ❌ {agent.name} error: {e}")
                        traceback.print_exc()

                if not agent_signals:
                    print(f"  ⚠️  No agent signals generated, skipping consensus")
                    continue

                # ── Layer 1 continued: Gemini LLM Agent ──
                # Runs after technical agents so it can synthesise their signals.
                if gemini_agent and gemini_agent._enabled:
                    try:
                        gemini_signal = gemini_agent.predict_signal_with_context(
                            df, symbol=stock, sentiment=sentiment, other_signals=agent_signals
                        )
                        agent_signals.append(gemini_signal)

                        g_pred = gemini_signal.get('prediction', 'HOLD')
                        g_conf = gemini_signal.get('confidence', 0)
                        g_reasoning = gemini_signal.get('reasoning', {})
                        g_reasoning_json = json.dumps(g_reasoning)

                        if os.getenv('DATABASE_URL'):
                            cursor.execute("""
                                INSERT INTO predictions
                                (symbol, prediction_date, target_date, agent_name, prediction, confidence, reasoning)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (symbol, prediction_date, target_date, agent_name)
                                DO UPDATE SET prediction = EXCLUDED.prediction,
                                             confidence = EXCLUDED.confidence,
                                             reasoning = EXCLUDED.reasoning
                            """, (stock, today, target, gemini_agent.name, g_pred, g_conf, g_reasoning_json))
                        else:
                            cursor.execute("""
                                INSERT OR REPLACE INTO predictions
                                (symbol, prediction_date, target_date, agent_name, prediction, confidence, reasoning)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (stock, today, target, gemini_agent.name, g_pred, g_conf, g_reasoning_json))

                        reasoning_short = g_reasoning.get('llm_reasoning', '')[:60]
                        print(f"  🤖 {gemini_agent.name}: {g_pred} ({g_conf:.0f}%) — {reasoning_short}")

                    except Exception as e:
                        print(f"  ⚠️  Gemini agent skipped for {stock}: {e}")

                # ── Compute market data for Risk Agent ──
                market_data = _compute_market_data(df)

                # ── Layers 2 & 3: Consensus Engine ──
                consensus_result = run_consensus(
                    symbol=stock,
                    agent_signals=agent_signals,
                    market_data=market_data,
                    sentiment_data=sentiment,
                    portfolio_signals=portfolio_signals,
                    risk_config=risk_cfg
                )

                # Track for portfolio-level risk checks on subsequent stocks
                portfolio_signals.append({
                    "symbol": stock,
                    "signal": consensus_result.get('final_signal', 'HOLD')
                })

                # Store consensus result
                _store_consensus(conn, stock, today, consensus_result)

                # Also store consensus as a "Consensus" prediction
                consensus_signal = consensus_result.get('final_signal', 'HOLD')
                consensus_confidence = consensus_result.get('confidence', 0)

                if os.getenv('DATABASE_URL'):
                    cursor.execute("""
                        INSERT INTO predictions
                        (symbol, prediction_date, target_date, agent_name, prediction, confidence)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, prediction_date, target_date, agent_name)
                        DO UPDATE SET prediction = EXCLUDED.prediction,
                                     confidence = EXCLUDED.confidence
                    """, (stock, today, target, "Consensus", consensus_signal, consensus_confidence))
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO predictions
                        (symbol, prediction_date, target_date, agent_name, prediction, confidence)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (stock, today, target, "Consensus", consensus_signal, consensus_confidence))

                # Display summary
                bull_s = consensus_result.get('bull_score', 0)
                bear_s = consensus_result.get('bear_score', 0)
                risk_action = consensus_result.get('risk_action', 'PASS')
                conviction = consensus_result.get('conviction', 'LOW')
                agreement = consensus_result.get('agent_agreement', 0)

                print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"  👥 Agreement: {agreement:.0%}  |  🛡️ Risk: {risk_action}")
                if consensus_result.get('risk_adjusted'):
                    print(f"  ⚠️  RISK-ADJUSTED (original signal was modified)")

        print(f"\n{'='*50}")
        print("🚀 Generating Daily Trade Recommendations...")
        try:
            generate_daily_trade_recommendations(today)
        except Exception as e:
            print(f"❌ Error generating trade recommendations: {e}")
            traceback.print_exc()

        print(f"\n{'='*50}")
        print("📋 Generating Daily Market Briefing...")
        try:
            generate_and_store_briefing(today)
        except Exception as e:
            print(f"❌ Error generating briefing: {e}")
            traceback.print_exc()

        print(f"\n{'='*50}")
        print("📊 Running Performance Evaluation...")
        try:
            from engines.evaluate_performance import run_evaluation
            run_evaluation(pipeline_run_id=f"run_{today}")
        except Exception as e:
            print(f"❌ Error running performance evaluation: {e}")
            traceback.print_exc()

        print(f"\n{'='*50}")
        print(f"✅ Pipeline complete! Processed {len(config.ALL_STOCKS)} stocks.")
        print(f"{'='*50}")

    except Exception as e:
        print(f"\n❌ Error in execute(): {e}")
        traceback.print_exc()
        sys.exit(1)


def get_market_data(symbol: str):
    """Fetch market data for risk calculation."""
    # Simplified: get latest price and 52w high from DB
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Latest close
        if os.getenv('DATABASE_URL'):
            cursor.execute("SELECT close FROM prices WHERE symbol = %s ORDER BY date DESC LIMIT 1", (symbol,))
        else:
            cursor.execute("SELECT close FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 1", (symbol,))
        
        row = cursor.fetchone()
        close = row['close'] if row else 0
        
        # 52w high
        # Calculate 52w high (approx 252 trading days)
        if os.getenv('DATABASE_URL'):
             cursor.execute("SELECT MAX(high) as high_52w FROM prices WHERE symbol = %s AND date >= CURRENT_DATE - INTERVAL '1 year'", (symbol,))
        else:
             cursor.execute("SELECT MAX(high) as high_52w FROM prices WHERE symbol = ? AND date >= date('now', '-1 year')", (symbol,))
        
        row_high = cursor.fetchone()
        high_52w = row_high['high_52w'] if row_high else 0
        
        # ATR (Simplified: 3% of close if not calculated)
        # In a real system, features.py would compute ATR and store it.
        # We'll stick to the default in trade_recommender if 0.
        atr = close * 0.03
        
        return {
            "close": close,
            "high_52w": high_52w,
            "atr": atr
        }

def open_new_position(user_id, rec, trading_date):
    """Create a new OPEN position."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if os.getenv('DATABASE_URL'):
            cursor.execute("""
                INSERT INTO user_positions (user_id, symbol, status, entry_date, entry_price)
                VALUES (%s, %s, 'OPEN', %s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, rec["symbol"], trading_date, rec.get("close_price")))
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO user_positions (user_id, symbol, status, entry_date, entry_price)
                VALUES (?, ?, 'OPEN', ?, ?)
            """, (user_id, rec["symbol"], trading_date, rec.get("close_price")))

def close_position(user_id, rec, trading_date):
    """Close an OPEN position."""
    exit_price = rec.get("close_price", 0)
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Calculate return logic requires reading entry price first or doing it in SQL
        # Doing in SQL for atomicity
        if os.getenv('DATABASE_URL'):
             cursor.execute("""
                UPDATE user_positions 
                SET status = 'CLOSED',
                    exit_date = %s,
                    exit_price = %s,
                    return_pct = CASE 
                        WHEN entry_price > 0 THEN ((%s - entry_price) / entry_price) * 100
                        ELSE 0
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s 
                AND symbol = %s 
                AND status = 'OPEN'
            """, (trading_date, exit_price, exit_price, user_id, rec["symbol"]))
        else:
             cursor.execute("""
                UPDATE user_positions 
                SET status = 'CLOSED',
                    exit_date = ?,
                    exit_price = ?,
                    return_pct = CASE 
                        WHEN entry_price > 0 THEN ((? - entry_price) / entry_price) * 100
                        ELSE 0
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? 
                AND symbol = ? 
                AND status = 'OPEN'
            """, (trading_date, exit_price, exit_price, user_id, rec["symbol"]))

def store_trade_recommendation(user_id, rec, trading_date):
    """Store recommendation to DB."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        query_pg = """
            INSERT INTO trade_recommendations (
                user_id, symbol, recommendation_date, action, signal, 
                confidence, conviction, risk_action, priority,
                close_price, stop_loss_pct, target_pct, 
                stop_loss_price, target_price, risk_reward_ratio,
                reasons, reasons_ar,
                bull_score, bear_score, agents_agreeing, agents_total, risk_flags
            ) VALUES (
                %s, %s, %s, %s, %s, 
                %s, %s, %s, %s,
                %s, %s, %s, 
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (user_id, symbol, recommendation_date) DO UPDATE SET
                action = EXCLUDED.action,
                signal = EXCLUDED.signal,
                confidence = EXCLUDED.confidence,
                conviction = EXCLUDED.conviction,
                priority = EXCLUDED.priority,
                reasons = EXCLUDED.reasons,
                reasons_ar = EXCLUDED.reasons_ar,
                updated_at = CURRENT_TIMESTAMP
        """
        
        query_sqlite = """
            INSERT INTO trade_recommendations (
                user_id, symbol, recommendation_date, action, signal, 
                confidence, conviction, risk_action, priority,
                close_price, stop_loss_pct, target_pct, 
                stop_loss_price, target_price, risk_reward_ratio,
                reasons, reasons_ar,
                bull_score, bear_score, agents_agreeing, agents_total, risk_flags
            ) VALUES (
                ?, ?, ?, ?, ?, 
                ?, ?, ?, ?,
                ?, ?, ?, 
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?
            )
            ON CONFLICT (user_id, symbol, recommendation_date) DO UPDATE SET
                action = excluded.action,
                signal = excluded.signal,
                confidence = excluded.confidence,
                conviction = excluded.conviction,
                priority = excluded.priority,
                reasons = excluded.reasons,
                reasons_ar = excluded.reasons_ar,
                updated_at = CURRENT_TIMESTAMP
        """
        
        params = (
            user_id, rec["symbol"], trading_date, rec["action"], rec["signal"],
            rec["confidence"], rec["conviction"], rec["risk_action"], rec["priority"],
            rec.get("close_price"), rec.get("stop_loss_pct"), rec.get("target_pct"),
            rec.get("stop_loss_price"), rec.get("target_price"), rec.get("risk_reward_ratio"),
            json.dumps(rec["reasons"]), json.dumps(rec["reasons_ar"]),
            rec["metadata"]["bull_score"], rec["metadata"]["bear_score"],
            rec["metadata"]["agents_agreeing"], rec["metadata"]["agents_total"],
            json.dumps(rec["metadata"].get("risk_flags", []))
        )
        
        if os.getenv('DATABASE_URL'):
            cursor.execute(query_pg, params)
        else:
            cursor.execute(query_sqlite, params)

from engines.trade_recommender import (
    generate_recommendation,
    score_recommendation_priority,
    calculate_risk_levels,
    TRADE_CONFIG
)
from engines.briefing_generator import generate_daily_briefing
from utils.trading_calendar import should_generate_recommendations


def generate_and_store_briefing(trading_date):
    """Gather data from DB, generate the daily briefing, and store it."""
    import time as _time
    start = _time.time()

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Rebuild consensus_map from DB (same pattern as trade recommendations)
        if os.getenv('DATABASE_URL'):
            cursor.execute("SELECT * FROM consensus_results WHERE prediction_date = %s", (trading_date,))
        else:
            cursor.execute("SELECT * FROM consensus_results WHERE prediction_date = ?", (trading_date,))

        consensus_rows = [dict(row) for row in cursor.fetchall()]
        if not consensus_rows:
            print("  ⚠️  No consensus results found — skipping briefing.")
            return

        consensus_map = {}
        for row in consensus_rows:
            for field in ['bull_case_json', 'bear_case_json', 'risk_assessment_json', 'agent_signals_json']:
                if isinstance(row.get(field), str):
                    try:
                        row[field] = json.loads(row[field])
                    except (json.JSONDecodeError, TypeError):
                        row[field] = {}

            consensus_map[row['symbol']] = {
                "final_signal": {
                    "prediction": row['final_signal'],
                    "confidence": row.get('confidence', 0),
                    "conviction": row.get('conviction')
                },
                "risk_assessment": {
                    "action": row.get('risk_action', 'PASS'),
                    "risk_score": row.get('risk_score', 0),
                    "risk_flags": (row.get('risk_assessment_json') or {}).get('risk_flags', [])
                },
                "bull_case": {"bull_score": row.get('bull_score', 0)},
                "bear_case": {"bear_score": row.get('bear_score', 0)},
                "bull_score": row.get('bull_score', 0),
                "bear_score": row.get('bear_score', 0),
                "risk_action": row.get('risk_action', 'PASS'),
                "risk_score": row.get('risk_score', 0),
                "confidence": row.get('confidence', 0)
            }

        # 2. Fetch stock metadata
        cursor.execute("SELECT symbol, name_en, name_ar, sector_en, sector_ar FROM egx30_stocks")
        stocks_metadata = {row['symbol']: dict(row) for row in cursor.fetchall()}

        # 3. Fetch latest 2 prices per stock
        prices_map = {}
        prev_prices_map = {}
        for symbol in consensus_map:
            if os.getenv('DATABASE_URL'):
                cursor.execute(
                    "SELECT date, close, volume FROM prices WHERE symbol = %s ORDER BY date DESC LIMIT 2",
                    (symbol,)
                )
            else:
                cursor.execute(
                    "SELECT date, close, volume FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 2",
                    (symbol,)
                )
            rows = [dict(r) for r in cursor.fetchall()]
            if rows:
                prices_map[symbol] = rows[0]
            if len(rows) > 1:
                prev_prices_map[symbol] = rows[1]

        # 4. Fetch latest sentiment
        sentiment_data = {}
        for symbol in consensus_map:
            if os.getenv('DATABASE_URL'):
                cursor.execute(
                    "SELECT avg_sentiment, sentiment_label, article_count FROM sentiment_scores WHERE symbol = %s ORDER BY date DESC LIMIT 1",
                    (symbol,)
                )
            else:
                cursor.execute(
                    "SELECT avg_sentiment, sentiment_label, article_count FROM sentiment_scores WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                    (symbol,)
                )
            row = cursor.fetchone()
            if row:
                sentiment_data[symbol] = dict(row)

        # 5. Generate briefing
        briefing = generate_daily_briefing(
            consensus_map, prices_map, prev_prices_map,
            stocks_metadata, sentiment_data
        )

        elapsed = round(_time.time() - start, 2)

        # 6. Store to DB
        if os.getenv('DATABASE_URL'):
            cursor.execute("""
                INSERT INTO daily_briefings
                (briefing_date, market_pulse_json, sector_breakdown_json,
                 risk_alerts_json, sentiment_snapshot_json,
                 stocks_processed, generation_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (briefing_date)
                DO UPDATE SET
                    market_pulse_json = EXCLUDED.market_pulse_json,
                    sector_breakdown_json = EXCLUDED.sector_breakdown_json,
                    risk_alerts_json = EXCLUDED.risk_alerts_json,
                    sentiment_snapshot_json = EXCLUDED.sentiment_snapshot_json,
                    stocks_processed = EXCLUDED.stocks_processed,
                    generation_time_seconds = EXCLUDED.generation_time_seconds
            """, (
                trading_date,
                json.dumps(briefing['market_pulse']),
                json.dumps(briefing['sector_breakdown']),
                json.dumps(briefing['risk_alerts']),
                json.dumps(briefing['sentiment_snapshot']),
                briefing['stocks_processed'],
                elapsed
            ))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_briefings
                (briefing_date, market_pulse_json, sector_breakdown_json,
                 risk_alerts_json, sentiment_snapshot_json,
                 stocks_processed, generation_time_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trading_date,
                json.dumps(briefing['market_pulse']),
                json.dumps(briefing['sector_breakdown']),
                json.dumps(briefing['risk_alerts']),
                json.dumps(briefing['sentiment_snapshot']),
                briefing['stocks_processed'],
                elapsed
            ))

        print(f"  ✅ Briefing stored ({briefing['stocks_processed']} stocks, {elapsed}s)")

def generate_daily_trade_recommendations(trading_date):
    """Generate trade recommendations."""
    
    # 1. Check calendar
    markets = should_generate_recommendations(datetime.strptime(trading_date, "%Y-%m-%d").date())
    print(f"  📅 Market Status: EGX={'OPEN' if markets['egx'] else 'CLOSED'}, US={'OPEN' if markets['us'] else 'CLOSED'}")
    
    # In this MVP, we process anyway if it's a weekday, but logically strict system would skip.
    # The prompt implies we should respect it.
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 2. Ensure active users have at least a baseline watchlist.
        if os.getenv('DATABASE_URL'):
            cursor.execute("SELECT id, email FROM users WHERE is_active = TRUE")
        else:
            cursor.execute("SELECT id, email FROM users WHERE is_active = 1")
        active_users = [dict(row) for row in cursor.fetchall()]

        if active_users:
            if os.getenv('DATABASE_URL'):
                cursor.execute("""
                    SELECT u.id
                    FROM users u
                    LEFT JOIN user_watchlist w ON u.id = w.user_id
                    WHERE u.is_active = TRUE
                    GROUP BY u.id
                    HAVING COUNT(w.id) = 0
                """)
            else:
                cursor.execute("""
                    SELECT u.id
                    FROM users u
                    LEFT JOIN user_watchlist w ON u.id = w.user_id
                    WHERE u.is_active = 1
                    GROUP BY u.id
                    HAVING COUNT(w.id) = 0
                """)
            users_without_watchlist = [row['id'] for row in cursor.fetchall()]

            if users_without_watchlist:
                cursor.execute("SELECT id FROM egx30_stocks ORDER BY id LIMIT 10")
                default_stock_ids = [row['id'] for row in cursor.fetchall()]

                for user_id in users_without_watchlist:
                    for stock_id in default_stock_ids:
                        if os.getenv('DATABASE_URL'):
                            cursor.execute("""
                                INSERT INTO user_watchlist (user_id, stock_id)
                                VALUES (%s, %s)
                                ON CONFLICT (user_id, stock_id) DO NOTHING
                            """, (user_id, stock_id))
                        else:
                            cursor.execute("""
                                INSERT OR IGNORE INTO user_watchlist (user_id, stock_id)
                                VALUES (?, ?)
                            """, (user_id, stock_id))
                print(f"  ✅ Seeded watchlists for {len(users_without_watchlist)} active users")

        # 3. Generate only for users that now have watchlist entries.
        if os.getenv('DATABASE_URL'):
            cursor.execute("SELECT DISTINCT u.id, u.email FROM users u JOIN user_watchlist w ON u.id = w.user_id WHERE u.is_active = TRUE")
        else:
            cursor.execute("SELECT DISTINCT u.id, u.email FROM users u JOIN user_watchlist w ON u.id = w.user_id WHERE u.is_active = 1")
        users = [dict(row) for row in cursor.fetchall()]
        print(f"  👥 Generating recommendations for {len(users)} users...")
        
        # Pre-fetch today's consensus results for ALL stocks to avoid N+1 queries
        # (This assumes run_consensus has populated consensus_results table)
        if os.getenv('DATABASE_URL'):
            cursor.execute("SELECT * FROM consensus_results WHERE prediction_date = %s", (trading_date,))
        else:
            cursor.execute("SELECT * FROM consensus_results WHERE prediction_date = ?", (trading_date,))
            
        consensus_rows = [dict(row) for row in cursor.fetchall()]
        # Map symbol -> consensus dict
        consensus_map = {}
        for row in consensus_rows:
            # Parse JSONs if string
            for field in ['bull_case_json', 'bear_case_json', 'risk_assessment_json', 'agent_signals_json']:
                 if isinstance(row.get(field), str):
                     row[field] = json.loads(row[field])
            
            # Reconstruct the dict structure expected by trade_recommender
            consensus_map[row['symbol']] = {
                "symbol": row['symbol'],
                "final_signal": {
                    "prediction": row['final_signal'],
                    "confidence": row['confidence'],
                    "conviction": row['conviction']
                },
                "risk_assessment": {
                    "action": row['risk_action'],
                    "risk_flags": row.get('risk_assessment_json', {}).get('risk_flags', [])
                },
                "bull_case": {"bull_score": row['bull_score']},
                "bear_case": {"bear_score": row['bear_score']},
                "agent_agreement": {
                    "agreeing": row['agents_agreeing'],
                    "total": row['agents_total']
                }
            }
        
    for user in users:
        user_id = user['id']
        max_positions = TRADE_CONFIG["max_open_positions"] # Default to free tier
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get watchlist
            if os.getenv('DATABASE_URL'):
                cursor.execute("SELECT s.symbol FROM user_watchlist w JOIN egx30_stocks s ON w.stock_id = s.id WHERE w.user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT s.symbol FROM user_watchlist w JOIN egx30_stocks s ON w.stock_id = s.id WHERE w.user_id = ?", (user_id,))
            watchlist = [row['symbol'] for row in cursor.fetchall()]
            
            # Get open positions
            if os.getenv('DATABASE_URL'):
                cursor.execute("SELECT symbol, entry_date, entry_price FROM user_positions WHERE user_id = %s AND status = 'OPEN'", (user_id,))
            else:
                cursor.execute("SELECT symbol, entry_date, entry_price FROM user_positions WHERE user_id = ? AND status = 'OPEN'", (user_id,))
            open_positions = [dict(row) for row in cursor.fetchall()]
            open_positions_map = {p['symbol']: p for p in open_positions}
            open_count = len(open_positions)
            
            # Get recent trades
            if os.getenv('DATABASE_URL'):
                 cursor.execute("SELECT symbol, action, recommendation_date as date FROM trade_recommendations WHERE user_id = %s AND recommendation_date >= CURRENT_DATE - INTERVAL '7 days'", (user_id,))
            else:
                 cursor.execute("SELECT symbol, action, recommendation_date as date FROM trade_recommendations WHERE user_id = ? AND recommendation_date >= date('now', '-7 days')", (user_id,))
            recent_trades = [dict(row) for row in cursor.fetchall()]
            
            user_recs = []
            
            for symbol in watchlist:
                # Market check
                mkt = 'egx' if symbol.endswith('.CA') else 'us'
                if not markets[mkt]:
                    continue # Skip closed market
                
                consensus = consensus_map.get(symbol)
                if not consensus:
                    continue
                
                market_data = get_market_data(symbol)
                
                rec = generate_recommendation(
                    symbol=symbol,
                    consensus=consensus,
                    current_position=open_positions_map.get(symbol),
                    recent_trades=recent_trades,
                    open_position_count=open_count,
                    max_positions=max_positions
                )
                
                # Add risk levels for BUY
                if rec["action"] == "BUY":
                    risk_levels = calculate_risk_levels(symbol, consensus, market_data)
                    rec.update(risk_levels)
                
                # Metadata
                rec["priority"] = score_recommendation_priority(rec)
                rec["close_price"] = market_data.get("close")
                user_recs.append(rec)
            
            # Sort
            user_recs.sort(key=lambda r: r["priority"], reverse=True)
            
            # Store & Update Positions
            for rec in user_recs:
                store_trade_recommendation(user_id, rec, trading_date)
                
                if rec["action"] == "BUY":
                    open_new_position(user_id, rec, trading_date)
                    open_count += 1
                elif rec["action"] == "SELL":
                    close_position(user_id, rec, trading_date)
                    open_count -= 1
            
            # Summary log
            buys = len([r for r in user_recs if r["action"] == "BUY"])
            sells = len([r for r in user_recs if r["action"] == "SELL"])
            print(f"    User {user_id}: {buys} BUY, {sells} SELL, {len(user_recs)-buys-sells} Other")


if __name__ == "__main__":
    try:
        execute()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
