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
from typing import Optional
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


def _detect_market_regime(conn) -> Optional[dict]:
    """
    Fit a Gaussian HMM on recent EGX30-representative returns to classify
    the current market regime as Calm / Turbulent / Crisis.

    Uses COMI.CA (Commercial International Bank) as a liquid EGX30 proxy when
    a dedicated EGX30 index price series is not available.

    Returns a dict with keys:
        regime_label_en   — "Calm", "Turbulent", or "Crisis"
        regime_label_ar   — Arabic equivalent
        regime_confidence — P(current state | data) in [0, 1]
        current_regime    — 0-indexed integer, vol-sorted
    Returns None on any failure (HMM not installed, insufficient data, etc.)
    """
    try:
        from engines.regime_model import RegimeModel, HAS_HMMLEARN
        if not HAS_HMMLEARN:
            return None

        # Try EGX30 index first, fall back to COMI.CA
        proxy_symbols = ['EGX30.CA', 'COMI.CA', 'HRHO.CA']
        price_series = None
        for sym in proxy_symbols:
            if os.getenv('DATABASE_URL'):
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT date, close FROM prices WHERE symbol=%s ORDER BY date", (sym,)
                )
            else:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT date, close FROM prices WHERE symbol=? ORDER BY date", (sym,)
                )
            rows = cursor.fetchall()
            if rows and len(rows) >= 100:
                df_proxy = pd.DataFrame(rows, columns=['date', 'close'])
                log_ret = np.log(df_proxy['close'] / df_proxy['close'].shift(1)).dropna()
                if len(log_ret) >= 100:
                    price_series = log_ret
                    break

        if price_series is None or len(price_series) < 100:
            return None

        import warnings
        regime_model = RegimeModel(use_auto_select=True, n_iter=100)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            state = regime_model.fit(price_series)

        result = state.to_dict()
        result['regime_label_en'] = state.regime_label_en
        result['regime_label_ar'] = state.regime_label_ar
        result['regime_confidence'] = state.regime_confidence
        result['current_regime'] = state.current_regime
        return result

    except Exception as e:
        logger.debug(f"Regime detection skipped: {e}")
        return None


import numpy as np
from typing import Optional


def _compute_garch_vol(symbol: str, df) -> float:
    """
    Fit a plain GARCH(1,1) model and return the one-step-ahead conditional
    volatility (sigma_t) in decimal form (e.g. 0.025 = 2.5% daily vol).

    Returns None if arch is not installed, data is insufficient, or fitting fails.
    Uses auto_select=False and model_preference="garch" to keep it fast (one model only).
    """
    try:
        import numpy as np
        from engines.garch_engine import GARCHEngine, HAS_ARCH
        if not HAS_ARCH or len(df) < 60:
            return None
        log_ret = np.log(df['close'] / df['close'].shift(1)).replace([np.inf, -np.inf], np.nan).dropna()
        if len(log_ret) < 60:
            return None
        returns_df = pd.DataFrame({symbol: log_ret})
        engine = GARCHEngine(model_preference="garch", use_auto_select=False, min_obs=60)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = engine.fit(returns_df)
        params = fitted.get(symbol)
        if params and params.model_type != "static":
            return params.sigma_t
    except Exception:
        pass
    return None


def _load_dynamic_weights(conn) -> dict:
    """
    Load accuracy-adjusted agent weights from the latest agent_performance_daily snapshot.
    Falls back to config.AGENT_WEIGHTS on SQLite or if insufficient data exists.

    Adjustment formula:
        adjusted_weight = base_weight * clamp(win_rate_30d / 50.0, 0.5, 2.0)
    Weights are renormalised to sum to 1.0 after adjustment.

    A minimum of 10 evaluated predictions is required before adjusting a given agent's weight;
    below that threshold the base weight is kept unchanged to avoid noise-driven swings.
    """
    base_weights = dict(getattr(config, 'AGENT_WEIGHTS', {
        "ML_RandomForest":    0.28,
        "MA_Crossover_Agent": 0.20,
        "RSI_Agent":          0.17,
        "Volume_Spike_Agent": 0.15,
        "Gemini_LLM_Agent":   0.20,
    }))

    if not os.getenv('DATABASE_URL'):
        return base_weights

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT ON (agent_name)
                agent_name, win_rate_30d, predictions_30d
            FROM agent_performance_daily
            ORDER BY agent_name, snapshot_date DESC
        """)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        if not rows:
            return base_weights

        snapshots = {}
        for row in rows:
            rec = row if isinstance(row, dict) else dict(zip(cols, row))
            snapshots[rec['agent_name']] = rec

        adjusted = {}
        for agent, base_w in base_weights.items():
            snap = snapshots.get(agent)
            preds = int(snap['predictions_30d'] or 0) if snap else 0
            win_rate = float(snap['win_rate_30d'] or 0) if snap else 0
            if snap and preds >= 10 and snap.get('win_rate_30d') is not None:
                multiplier = max(0.5, min(2.0, win_rate / 50.0))
                adjusted[agent] = base_w * multiplier
            else:
                adjusted[agent] = base_w

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: round(v / total, 4) for k, v in adjusted.items()}

        return adjusted
    except Exception as e:
        logger.warning(f"Could not load dynamic agent weights: {e}")
        return base_weights


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
            (symbol, prediction_date, final_signal, conviction, confidence, xmore_score,
             risk_adjusted, agent_agreement, agents_agreeing, agents_total,
             majority_direction, bull_score, bear_score, risk_action, risk_score,
             bull_case_json, bear_case_json, risk_assessment_json,
             agent_signals_json, reasoning_chain_json, display_json)
            VALUES (%s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s)
            ON CONFLICT (symbol, prediction_date)
            DO UPDATE SET
                final_signal = EXCLUDED.final_signal,
                conviction = EXCLUDED.conviction,
                confidence = EXCLUDED.confidence,
                xmore_score = EXCLUDED.xmore_score,
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
            consensus_result.get('xmore_score', 0),
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
            (symbol, prediction_date, final_signal, conviction, confidence, xmore_score,
             risk_adjusted, agent_agreement, agents_agreeing, agents_total,
             majority_direction, bull_score, bear_score, risk_action, risk_score,
             bull_case_json, bear_case_json, risk_assessment_json,
             agent_signals_json, reasoning_chain_json, display_json)
            VALUES (?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?)
        """, (
            stock, today,
            consensus_result.get('final_signal', 'HOLD'),
            consensus_result.get('conviction', 'LOW'),
            consensus_result.get('confidence', 0),
            consensus_result.get('xmore_score', 0),
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
            # Pull latest Telegram posts into news table before agents read sentiment
            try:
                from engines.telegram_reader import run_telegram_pipeline
                run_telegram_pipeline(conn, hours_back=25)
            except Exception as _tg_err:
                print(f"[TELEGRAM] Skipped: {_tg_err}")

            # ── Intelligence pipeline (news + fundamentals + insider) ──────
            try:
                from agents.intelligence.run_intelligence import run_intelligence_pipeline
                intel = run_intelligence_pipeline(conn)
                MATERIAL_TICKERS = intel.get("material_tickers", [])
                print(f"[INTEL] {intel.get('stored', 0)} new articles | "
                      f"{len(MATERIAL_TICKERS)} material tickers")
            except Exception as _intel_err:
                MATERIAL_TICKERS = []
                print(f"[INTEL] Skipped: {_intel_err}")
            # ──────────────────────────────────────────────────────────────

            # Load accuracy-adjusted weights once for the entire run
            dynamic_weights = _load_dynamic_weights(conn)
            base_weights = getattr(config, 'AGENT_WEIGHTS', {})
            if dynamic_weights != base_weights:
                print(f"Dynamic agent weights (accuracy-adjusted): {dynamic_weights}")
            else:
                print("Using base agent weights (no accuracy data yet)")

            # Detect market-wide regime once — applies as a filter across all stocks
            market_regime = _detect_market_regime(conn)
            if market_regime:
                lbl = market_regime.get('regime_label_en', 'Unknown')
                conf = market_regime.get('regime_confidence', 0)
                print(f"Market Regime: {lbl} ({conf:.1%} confidence) "
                      f"[regime {market_regime.get('current_regime')}/"
                      f"{market_regime.get('n_regimes', '?')-1}]")
            else:
                print("Market Regime: detection unavailable (hmmlearn not installed or insufficient data)")

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

                # Enrich with GARCH one-step-ahead conditional vol forecast
                if market_data:
                    garch_vol = _compute_garch_vol(stock, df)
                    if garch_vol is not None:
                        market_data['garch_forecast_vol'] = garch_vol
                        print(f"  📐 GARCH forecast vol: {garch_vol:.2%} (hist 20d: {market_data.get('volatility_20d', 0):.2%})")

                # ── Layers 2 & 3: Consensus Engine ──
                consensus_result = run_consensus(
                    symbol=stock,
                    agent_signals=agent_signals,
                    market_data=market_data,
                    sentiment_data=sentiment,
                    portfolio_signals=portfolio_signals,
                    risk_config=risk_cfg,
                    dynamic_weights=dynamic_weights,
                    market_regime=market_regime,
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
        print("📡 Generating ETF Signals...")
        try:
            from engines.agent_etf_signal import run_etf_signals
            with get_connection() as _etf_conn:
                n_etf = run_etf_signals(_etf_conn)
            print(f"[ETF] Generated {n_etf} ETF signals")
        except Exception as _etf_err:
            print(f"[ETF] Skipped: {_etf_err}")

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

def get_ohlc_df(symbol: str, limit: int = 60) -> Optional[pd.DataFrame]:
    """Fetch recent OHLC data for pivot / ATR calculation."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if os.getenv('DATABASE_URL'):
                cursor.execute(
                    "SELECT date, open, high, low, close, volume FROM prices "
                    "WHERE symbol = %s ORDER BY date DESC LIMIT %s",
                    (symbol, limit)
                )
            else:
                cursor.execute(
                    "SELECT date, open, high, low, close, volume FROM prices "
                    "WHERE symbol = ? ORDER BY date DESC LIMIT ?",
                    (symbol, limit)
                )
            rows = cursor.fetchall()
        if not rows:
            return None
        if os.getenv('DATABASE_URL'):
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        return df.sort_values('date').reset_index(drop=True)
    except Exception:
        return None


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
                bull_score, bear_score, agents_agreeing, agents_total, risk_flags,
                trend_ar, trend_en, rec_type_ar, rec_type_en,
                buy_guide, pivot, r1, r2, s1, s2, patterns
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (user_id, symbol, recommendation_date) DO UPDATE SET
                action = EXCLUDED.action,
                signal = EXCLUDED.signal,
                confidence = EXCLUDED.confidence,
                conviction = EXCLUDED.conviction,
                priority = EXCLUDED.priority,
                reasons = EXCLUDED.reasons,
                reasons_ar = EXCLUDED.reasons_ar,
                trend_ar = EXCLUDED.trend_ar,
                trend_en = EXCLUDED.trend_en,
                rec_type_ar = EXCLUDED.rec_type_ar,
                rec_type_en = EXCLUDED.rec_type_en,
                buy_guide = EXCLUDED.buy_guide,
                pivot = EXCLUDED.pivot,
                r1 = EXCLUDED.r1, r2 = EXCLUDED.r2,
                s1 = EXCLUDED.s1, s2 = EXCLUDED.s2,
                patterns = EXCLUDED.patterns,
                updated_at = CURRENT_TIMESTAMP
        """

        query_sqlite = """
            INSERT INTO trade_recommendations (
                user_id, symbol, recommendation_date, action, signal,
                confidence, conviction, risk_action, priority,
                close_price, stop_loss_pct, target_pct,
                stop_loss_price, target_price, risk_reward_ratio,
                reasons, reasons_ar,
                bull_score, bear_score, agents_agreeing, agents_total, risk_flags,
                trend_ar, trend_en, rec_type_ar, rec_type_en,
                buy_guide, pivot, r1, r2, s1, s2, patterns
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT (user_id, symbol, recommendation_date) DO UPDATE SET
                action = excluded.action,
                signal = excluded.signal,
                confidence = excluded.confidence,
                conviction = excluded.conviction,
                priority = excluded.priority,
                reasons = excluded.reasons,
                reasons_ar = excluded.reasons_ar,
                trend_ar = excluded.trend_ar,
                trend_en = excluded.trend_en,
                rec_type_ar = excluded.rec_type_ar,
                rec_type_en = excluded.rec_type_en,
                buy_guide = excluded.buy_guide,
                pivot = excluded.pivot,
                r1 = excluded.r1, r2 = excluded.r2,
                s1 = excluded.s1, s2 = excluded.s2,
                patterns = excluded.patterns,
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
            json.dumps(rec["metadata"].get("risk_flags", [])),
            rec.get("trend_ar"), rec.get("trend_en"),
            rec.get("rec_type_ar"), rec.get("rec_type_en"),
            rec.get("buy_guide"), rec.get("pivot"),
            rec.get("r1"), rec.get("r2"), rec.get("s1"), rec.get("s2"),
            json.dumps(rec.get("patterns", [])),
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
from engines.pivot_engine import enrich_recommendation
from engines.briefing_generator import generate_daily_briefing
from utils.trading_calendar import should_generate_recommendations

# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL INVESTOR SCORING LAYER — composite score + 6 output modes (v1.0)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from engines.scoring_formatter import (
        ScoringFormatter, calculate_composite_score, derive_components_from_rec
    )
    _SCORING_ENABLED = True
except Exception as _sc_err:
    logger.warning(f"Scoring formatter not available: {_sc_err}")
    _SCORING_ENABLED = False


def _populate_scored_signals(recs: list, conn, regime: str = "NEUTRAL") -> None:
    """
    Upsert composite scores for today's approved recommendations into scored_signals.
    Uses ON CONFLICT (symbol, signal_date) DO UPDATE to handle reruns gracefully.
    """
    if not _SCORING_ENABLED or not recs:
        return
    try:
        cursor = conn.cursor()
        ph = "%s" if os.getenv("DATABASE_URL") else "?"
        is_pg = bool(os.getenv("DATABASE_URL"))

        sf = ScoringFormatter("standard_100")

        for rec in recs:
            try:
                components = derive_components_from_rec(rec, regime=regime)
                entry      = sf.build_scored_entry(rec.get("symbol", ""), rec, components)

                import json
                all_fmt_json = json.dumps(entry["all_formats"])

                if is_pg:
                    cursor.execute("SAVEPOINT sc_upsert")
                    upsert_sql = f"""
                        INSERT INTO scored_signals
                            (symbol, signal_date, action, composite_score, scoring_mode,
                             score_value, consensus_score, execution_score, regime_score,
                             momentum_score, meets_threshold, all_formats)
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                        ON CONFLICT (symbol, signal_date)
                        DO UPDATE SET
                            composite_score = EXCLUDED.composite_score,
                            score_value     = EXCLUDED.score_value,
                            all_formats     = EXCLUDED.all_formats,
                            meets_threshold = EXCLUDED.meets_threshold
                    """
                else:
                    upsert_sql = f"""
                        INSERT OR REPLACE INTO scored_signals
                            (symbol, signal_date, action, composite_score, scoring_mode,
                             score_value, consensus_score, execution_score, regime_score,
                             momentum_score, meets_threshold, all_formats)
                        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                    """

                cursor.execute(upsert_sql, (
                    entry["symbol"],
                    entry["signal_date"],
                    entry["action"],
                    entry["composite_score"],
                    entry["scoring_mode"],
                    entry["score_value"],
                    entry["consensus_score"],
                    entry["execution_score"],
                    entry["regime_score"],
                    entry["momentum_score"],
                    entry["meets_threshold"],
                    all_fmt_json,
                ))

                if is_pg:
                    cursor.execute("RELEASE SAVEPOINT sc_upsert")

            except Exception as row_err:
                if is_pg:
                    try:
                        cursor.execute("ROLLBACK TO SAVEPOINT sc_upsert")
                    except Exception:
                        pass
                logger.warning(f"scored_signals upsert failed for {rec.get('symbol')}: {row_err}")

        conn.commit()
        logger.info(f"  [SCORING] {len(recs)} signals scored and stored")
    except Exception as e:
        logger.warning(f"_populate_scored_signals failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION REALISM LAYER — friction-adjusted signals (v1.0)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from engines.execution_agent import ExecutionAgent
    from engines.regime_filter import RegimeFilter
    _EXECUTION_REALISM_ENABLED = True
except Exception as _er_err:
    logger.warning(f"Execution realism layer not available: {_er_err}")
    _EXECUTION_REALISM_ENABLED = False


def _log_blocked_signal(signal: dict, conn, regime_info: str = ""):
    """Persist a blocked signal to the blocked_signals audit table."""
    try:
        cursor = conn.cursor()
        ph = "%s" if os.getenv("DATABASE_URL") else "?"
        cursor.execute(
            f"""
            INSERT INTO blocked_signals
                (ticker, action, signal_date, consensus_score, block_reason,
                 raw_price, expected_return, edge_ratio, regime_at_block)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
            """,
            (
                signal.get("ticker", signal.get("symbol", "")),
                signal.get("action", ""),
                signal.get("date", ""),
                signal.get("consensus_score", signal.get("confidence", 0)),
                signal.get("block_reason", ""),
                signal.get("raw_price", signal.get("close_price", 0)),
                signal.get("expected_return_pct", signal.get("target_pct", 0)),
                signal.get("edge_ratio", None),
                regime_info,
            ),
        )
    except Exception as e:
        logger.debug(f"[ExecRealism] Could not log blocked signal: {e}")


def _fetch_market_data_for_exec(symbol: str, conn) -> dict:
    """Pull avg_daily_volume and prev_close from DB for execution checks."""
    try:
        cursor = conn.cursor()
        ph = "%s" if os.getenv("DATABASE_URL") else "?"
        if os.getenv("DATABASE_URL"):
            cursor.execute(
                """SELECT close, volume FROM prices WHERE symbol = %s
                   ORDER BY date DESC LIMIT 20""",
                (symbol,),
            )
        else:
            cursor.execute(
                "SELECT close, volume FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 20",
                (symbol,),
            )
        rows = cursor.fetchall()
        if not rows:
            return {}
        volumes = [r["volume"] for r in rows if r.get("volume")]
        avg_vol = int(sum(volumes) / len(volumes)) if volumes else 0
        prev_close = rows[0]["close"] if rows else 0
        return {"avg_daily_volume": avg_vol, "prev_close": prev_close}
    except Exception as e:
        logger.debug(f"[ExecRealism] market data fetch error for {symbol}: {e}")
        return {}


def apply_execution_realism(
    recs: list, conn, portfolio_value_egp: float = 500_000.0
) -> list:
    """
    Gates all BUY recommendations through execution realism checks.
    SELL and HOLD pass through unchanged.
    Returns list of approved recs (with adjusted fill prices for BUYs).
    """
    if not _EXECUTION_REALISM_ENABLED:
        return recs

    exec_agent     = ExecutionAgent(portfolio_value_egp=portfolio_value_egp)
    regime_filter  = RegimeFilter()
    approved       = []

    # Check market regime once for all BUY signals
    long_allowed, regime_reason = regime_filter.is_long_allowed()
    regime_info = regime_filter.get_current_regime()
    regime_str  = regime_info.get("regime", "UNKNOWN")

    for rec in recs:
        action = (rec.get("action") or "HOLD").upper()

        # Non-BUY signals pass through without execution checks
        if action != "BUY":
            rec["execution_approved"] = True
            approved.append(rec)
            continue

        # Regime gate
        if not long_allowed:
            rec["blocked"]            = True
            rec["block_reason"]       = f"REGIME_FILTER: {regime_reason}"
            rec["execution_approved"] = False
            _log_blocked_signal(rec, conn, regime_str)
            logger.info(f"  [BLOCKED] {rec.get('symbol')} — {rec['block_reason']}")
            continue

        # Fetch market data
        market_data = _fetch_market_data_for_exec(rec.get("symbol", ""), conn)
        if not market_data:
            rec["execution_approved"] = True  # fail-open if no data
            approved.append(rec)
            continue

        market_data["portfolio_value_egp"] = portfolio_value_egp

        # Build signal dict for execution agent
        signal = {
            "ticker":              rec.get("symbol", ""),
            "action":              action,
            "raw_price":           rec.get("close_price") or 0,
            "expected_return_pct": (rec.get("target_pct") or 0) / 100,
            "stop_loss_pct":       (rec.get("stop_loss_pct") or 0) / 100,
            "consensus_score":     rec.get("confidence") or 0,
        }

        result = exec_agent.evaluate_signal(signal, market_data)

        if result["approved"]:
            rec.update({
                "realistic_fill_price": result["realistic_fill_price"],
                "position_value_egp":   result["position_value_egp"],
                "round_trip_cost_egp":  result["round_trip_cost_egp"],
                "edge_ratio":           result["edge_ratio"],
                "split_required":       result["split_required"],
                "realistic_stop_price": result["realistic_stop_price"],
                "execution_approved":   True,
            })
            logger.info(
                f"  [APPROVED] {rec.get('symbol')} fill={result['realistic_fill_price']:.4f} "
                f"edge={result['edge_ratio']}x"
            )
            approved.append(rec)
        else:
            rec["blocked"]            = True
            rec["block_reason"]       = result["rejection_reason"]
            rec["execution_approved"] = False
            rec["edge_ratio"]         = result["edge_ratio"]
            _log_blocked_signal(rec, conn, regime_str)
            logger.info(f"  [BLOCKED] {rec.get('symbol')} — {result['rejection_reason']}")

    return approved


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

                # Add pivot levels, trend, buy guide, recommendation type
                ohlc_df = get_ohlc_df(symbol)
                if ohlc_df is not None:
                    enrich_recommendation(rec, ohlc_df, market_data.get("close", 0))

                # Metadata
                rec["priority"] = score_recommendation_priority(rec)
                rec["close_price"] = market_data.get("close")
                user_recs.append(rec)
            
            # Sort
            user_recs.sort(key=lambda r: r["priority"], reverse=True)

            # ── Execution realism gate ─────────────────────────────────────
            user_recs = apply_execution_realism(user_recs, conn)
            # Material event bonus
            for rec in user_recs:
                if rec.get("symbol") in MATERIAL_TICKERS:
                    rec["composite_score"] = min(1.0, (rec.get("composite_score") or 0.5) * 1.15)
                    flags = rec.get("flags", [])
                    if "⚡MATERIAL_EVENT" not in flags:
                        flags.append("⚡MATERIAL_EVENT")
                    rec["flags"] = flags
            # ──────────────────────────────────────────────────────────────

            # ── Universal Investor Scoring ─────────────────────────────────
            _populate_scored_signals(user_recs, conn)
            # ──────────────────────────────────────────────────────────────

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
