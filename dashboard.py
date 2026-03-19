import streamlit as st
import pandas as pd
import sqlite3
import altair as alt
from datetime import datetime, timedelta
import config
import prediction_utils as utils

# Page Config
st.set_page_config(page_title="Xmore2 Dashboard", page_icon="🇪🇬", layout="wide")

# Database Connection
@st.cache_data
def load_data():
    conn = utils.get_db_connection()
    
    # Prices
    prices = pd.read_sql("SELECT * FROM prices", conn)
    prices['date'] = pd.to_datetime(prices['date'])
    
    # Predictions
    preds = pd.read_sql("SELECT * FROM predictions", conn)
    
    # Evaluations
    evals = pd.read_sql("SELECT * FROM evaluations", conn)
    
    conn.close()
    return prices, preds, evals

try:
    prices, preds, evals = load_data()
except Exception as e:
    st.error(f"Error loading database: {e}")
    st.stop()

# Header
st.title("🇪🇬 Xmore2 Trading Dashboard")
st.markdown("**Focus:** Egyptian Exchange (EGX) | **Horizon:** 5 Days")

# Top Stats
col1, col2, col3, col4 = st.columns(4)
col1.metric("Stocks Tracked", len(prices['symbol'].unique()))
col2.metric("Total Predictions", len(preds))
accuracy = 0
if len(evals) > 0:
    accuracy = (evals['was_correct'].sum() / len(evals)) * 100
col3.metric("Overall Accuracy", f"{accuracy:.1f}%")
latest_date = prices['date'].max().strftime('%Y-%m-%d')
col4.metric("Latest Data", latest_date)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Comparison: Future vs History", "📈 Price Charts", "🧐 Detailed Evaluation", "⚙️ Execution Quality"])

with tab1:
    st.header("🔮 Future Targets vs 📜 Historical Reality")
    
    col_future, col_history = st.columns(2)
    
    with col_future:
        st.subheader("Future Targets (+5 Days)")
        st.caption(f"Predictions targeting: **{(datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')}**")
        
        # Get active predictions (future target dates)
        future_preds = preds[preds['target_date'] > datetime.now().strftime('%Y-%m-%d')].sort_values('prediction_date', ascending=False).head(10)
        
        if len(future_preds) > 0:
            st.dataframe(future_preds[['symbol', 'agent_name', 'prediction', 'target_date']], use_container_width=True)
        else:
            st.info("No active future predictions found.")

    with col_history:
        lookback_date = utils.get_target_lookback_date(7)
        st.subheader("One Week Ago (Historical)")
        st.caption(f"What happened to predictions targeting: **{lookback_date}**?")
        
        # 1. Find preds targeting this past date
        past_target_preds = preds[preds['target_date'] == lookback_date].copy()
        
        if len(past_target_preds) > 0:
            # 2. Calculate outcomes on the fly
            results = []
            for _, row in past_target_preds.iterrows():
                symbol = row['symbol']
                start_date = row['prediction_date']
                
                # Get prices
                start_row = prices[(prices['symbol'] == symbol) & (prices['date'] == start_date)]
                end_row = prices[(prices['symbol'] == symbol) & (prices['date'] == lookback_date)]
                
                if not start_row.empty and not end_row.empty:
                    s_price = start_row.iloc[0]['close']
                    e_price = end_row.iloc[0]['close']
                    outcome, correct, pct = utils.calculate_outcome(s_price, e_price, row['prediction'])
                    
                    results.append({
                        'Symbol': symbol,
                        'Agent': row['agent_name'],
                        'Pred': row['prediction'],
                        'Actual': outcome,
                        'Change': f"{pct:.2f}%",
                        'Correct': "✅" if correct else "❌"
                    })
            
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
            else:
                st.warning("Found predictions but missing price data to verify them.")
        else:
            st.info(f"No predictions found that targeted {lookback_date}")

with tab2:
    st.header("Price History & Signals")
    selected_stock = st.selectbox("Select Stock", config.ALL_STOCKS)
    
    stock_data = prices[prices['symbol'] == selected_stock].sort_values('date')
    
    # Base Price Chart
    base = alt.Chart(stock_data).encode(x='date:T')
    
    line = base.mark_line().encode(
        y=alt.Y('close:Q', scale=alt.Scale(zero=False)),
        tooltip=['date', 'close', 'volume']
    )
    
    # Volume Bar Chart
    bar = base.mark_bar(opacity=0.3).encode(
        y=alt.Y('volume:Q', axis=alt.Axis(title='Volume')),
        color=alt.value('gray')
    )
    
    st.altair_chart((line + bar).interactive(), use_container_width=True)

with tab3:
    st.header("Evaluation Metrics")
    
    # Lookback Tool
    st.subheader("🗓️ Look-back Analysis")
    days_back = st.slider("Target Date Lookback (Days Ago)", 3, 30, 7)
    target_dt = (datetime.now() - pd.Timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    st.caption(f"Analyzing predictions that targeted: **{target_dt}**")
    
    # Filter evals for this target date
    # Note: We need to join preds to get target_date if not present in evals fully, 
    # but let's assume simple filtering for now or use the DB logic logic roughly here
    
    # In dashboard we loaded raw tables. 
    # Let's filter predictions that had this target_date and join with evals
    target_preds = preds[preds['target_date'] == target_dt]
    
    if len(target_preds) == 0:
        st.warning(f"No predictions found targeting {target_dt}")
    else:
        # Check if they have evaluations
        relevant_evals = evals[evals['prediction_id'].isin(target_preds['id'])]
        
        if len(relevant_evals) > 0:
            acc = (relevant_evals['was_correct'].sum() / len(relevant_evals)) * 100
            st.metric("Batch Accuracy", f"{acc:.1f}%", f"{len(relevant_evals)} evaluated")
            
            st.dataframe(relevant_evals[['symbol', 'agent_name', 'prediction', 'actual_outcome', 'was_correct', 'actual_change_pct']])
        else:
            st.info("Predictions exist but haven't been evaluated yet (or data missing). Run `python evaluate.py`")
            st.dataframe(target_preds)

# Sidebar
st.sidebar.markdown("### ℹ️ About")
st.sidebar.info("Xmore2 is a hobby-grade system for the EGX. Use for educational purposes only.")
st.sidebar.markdown("---")
with tab4:
    st.header("⚙️ Execution Quality")
    st.caption("Friction-adjusted signal analysis — EGX-specific transaction costs, slippage, and regime filtering.")

    # ── 1. Regime Status (P6 — enhanced with confidence + per-regime accuracy) ──
    st.subheader("📡 Market Regime (EGX30)")
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from engines.regime_filter import RegimeFilter
        rf = RegimeFilter()
        regime_info = rf.get_current_regime()
        regime = regime_info.get("regime", "UNKNOWN")
        regime_color = {"BULL": "🟢", "NEUTRAL": "🟡", "BEAR": "🔴"}.get(regime, "⚪")
        dist_pct = regime_info.get("distance_from_ma_pct", 0)

        # Confidence: distance from MA threshold expressed as 0–100 score
        #   BULL: positive distance → closer to 0 = weak, further positive = stronger
        #   BEAR: negative distance → more negative = stronger bear
        raw_distance = abs(dist_pct)
        regime_confidence = min(100, int(50 + raw_distance * 5))  # 50 at threshold, +5 per %

        col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
        col_r1.metric("Regime", f"{regime_color} {regime}")
        col_r2.metric("EGX30 Price", f"{regime_info.get('egx30_price', 'N/A'):,}" if regime_info.get("egx30_price") else "N/A")
        col_r3.metric("MA20", f"{regime_info.get('ma20', 'N/A'):,}" if regime_info.get("ma20") else "N/A")
        col_r4.metric("Distance from MA", f"{dist_pct:.1f}%")
        col_r5.metric("Regime Confidence", f"{regime_confidence}%")

        longs_ok = regime_info.get("new_longs_allowed", False)
        if longs_ok:
            st.success("✅ New long positions ALLOWED")
        else:
            st.error("🚫 New long positions BLOCKED — market not in BULL regime")

        # Per-regime historical accuracy from evaluations DB
        st.caption("**Per-regime historical signal accuracy (last 90 days)**")
        try:
            conn_regime = sqlite3.connect("stocks.db")
            regime_acc_df = pd.read_sql(
                """SELECT e.regime_at_signal,
                          COUNT(*) as total,
                          SUM(CASE WHEN e.was_correct = 1 THEN 1 ELSE 0 END) as correct,
                          ROUND(100.0 * SUM(CASE WHEN e.was_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct
                   FROM evaluations e
                   WHERE e.regime_at_signal IS NOT NULL
                     AND e.evaluation_date >= date('now', '-90 days')
                   GROUP BY e.regime_at_signal
                   ORDER BY accuracy_pct DESC""",
                conn_regime
            )
            conn_regime.close()
            if regime_acc_df.empty:
                st.info("No per-regime accuracy data yet.")
            else:
                regime_acc_df.columns = ["Regime at Signal", "Total Signals", "Correct", "Accuracy %"]
                st.dataframe(regime_acc_df, use_container_width=True, hide_index=True)
        except Exception as ex:
            st.caption(f"Per-regime accuracy unavailable: {ex}")

    except Exception as e:
        st.warning(f"Regime filter unavailable: {e}")

    st.divider()

    # ── 2. Net vs Gross Performance (P1) ──────────────────────────────────────
    st.subheader("📊 Net vs Gross Performance")
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from engines.performance_metrics import get_performance_summary

        period_days = st.slider("Analysis period (days)", 7, 90, 30, key="exec_period")
        perf = get_performance_summary(days=period_days)
        if perf:
            col_p1, col_p2, col_p3, col_p4, col_p5, col_p6 = st.columns(6)
            gross_ret = perf.get("avg_return_1d", 0) or 0
            net_ret   = perf.get("avg_return_1d_net", 0) or 0
            gross_sr  = perf.get("sharpe_ratio", 0) or 0
            net_sr    = perf.get("sharpe_ratio_net", 0) or 0
            prof_acc  = perf.get("profitability_accuracy", 0) or 0
            cost_drag = perf.get("cost_drag_total_pct", 0) or 0
            prof_acc_pct = prof_acc * 100 if prof_acc <= 1 else prof_acc

            col_p1.metric("Gross Avg Return", f"{gross_ret:.2f}%")
            col_p2.metric("Net Avg Return",   f"{net_ret:.2f}%",
                          delta=f"{net_ret - gross_ret:.2f}%")
            col_p3.metric("Gross Sharpe",     f"{gross_sr:.2f}")
            col_p4.metric("Net Sharpe",       f"{net_sr:.2f}",
                          delta=f"{net_sr - gross_sr:.2f}")
            col_p5.metric("Profitability %",  f"{prof_acc_pct:.1f}%",
                          help="Fraction of directional trades profitable after transaction costs")
            col_p6.metric("Total Cost Drag",  f"{cost_drag:.2f}%",
                          help="Cumulative cost drag across all signals in the period")
        else:
            st.info("Performance data not available for the selected period.")
    except Exception as e:
        st.info(f"Net/Gross performance unavailable: {e}")

    st.divider()

    # ── 3. Execution Filter Stats (P8) ────────────────────────────────────────
    st.subheader("🔍 Execution Filter Statistics")
    try:
        from engines.performance_metrics import get_execution_filter_stats
        filter_stats = get_execution_filter_stats(days=locals().get("period_days", 30))
        if filter_stats:
            col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
            total   = filter_stats.get("total", filter_stats.get("total_signals", 0)) or 0
            approved = filter_stats.get("approved", filter_stats.get("approved_count", 0)) or 0
            blocked = filter_stats.get("blocked_by_edge", filter_stats.get("blocked_count", 0)) or 0
            split   = filter_stats.get("split_required", filter_stats.get("split_count", 0)) or 0
            blocked_pct = filter_stats.get("blocked_pct", None)
            if blocked_pct is None:
                blocked_pct = (blocked / total * 100) if total > 0 else 0
            col_f1.metric("Total Signals", int(total))
            col_f2.metric("Approved",  int(approved if approved else max(total - blocked, 0)))
            col_f3.metric("Blocked by Edge",   int(blocked),
                          delta=f"{blocked_pct:.1f}%",
                          delta_color="inverse")
            col_f4.metric("Split/Scaled", int(split))
            col_f5.metric("Edge Ratio Avg", f"{filter_stats.get('avg_edge_ratio', 0) or 0:.2f}")

            if blocked_pct > 40:
                st.warning(
                    f"⚠️ {blocked_pct:.0f}% of signals are being blocked. "
                    "Review regime filter and execution thresholds."
                )
            edge_min = filter_stats.get("min_edge_ratio", None)
            edge_max = filter_stats.get("max_edge_ratio", None)
            if edge_min is not None and edge_max is not None:
                st.caption(f"Edge ratio range: **{edge_min:.2f}** – **{edge_max:.2f}**")
        else:
            st.info("No execution filter data available for the selected period.")
    except Exception as e:
        st.info(f"Execution filter stats unavailable: {e}")

    st.divider()

    # ── 4. Friction Cost Summary ──────────────────────────────────────────────
    st.subheader("💸 Friction Cost Summary")
    try:
        conn_exec = sqlite3.connect("stocks.db")
        cutoff = (datetime.now() - timedelta(days=locals().get("period_days", 30))).strftime("%Y-%m-%d")

        cost_df = pd.read_sql(
            """SELECT SUM(round_trip_cost_egp) as total_cost,
                      AVG(round_trip_cost_egp / NULLIF(position_value_egp,0) * 100) as avg_cost_pct,
                      COUNT(*) as total_signals,
                      SUM(CASE WHEN execution_approved = 0 THEN 1 ELSE 0 END) as blocked_count
               FROM trade_recommendations
               WHERE recommendation_date >= ?""",
            conn_exec, params=[cutoff]
        )
        row = cost_df.iloc[0]
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        col_c1.metric("Total Round-Trip Costs", f"EGP {row.get('total_cost') or 0:,.0f}")
        col_c2.metric("Avg Cost % of Position", f"{row.get('avg_cost_pct') or 0:.3f}%")
        col_c3.metric("Total Signals", int(row.get("total_signals") or 0))
        col_c4.metric("Signals Blocked", int(row.get("blocked_count") or 0))
    except Exception as e:
        st.info(f"Cost data not available: {e}")

    st.divider()

    # ── 5. Sector Concentration (P7) ─────────────────────────────────────────
    st.subheader("🏗️ Sector Concentration")
    try:
        conn_sector = sqlite3.connect("stocks.db")
        sector_cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        sector_raw = pd.read_sql(
            """SELECT sector_en,
                      COUNT(*) as signal_count,
                      AVG(COALESCE(kelly_fraction, position_size_pct, 0.08)) as avg_alloc
               FROM trade_recommendations
               WHERE recommendation_date >= ?
                 AND (execution_approved = 1 OR execution_approved IS NULL)
                 AND sector_en IS NOT NULL
               GROUP BY sector_en
               ORDER BY signal_count DESC""",
            conn_sector, params=[sector_cutoff]
        )
        conn_sector.close()

        if sector_raw.empty:
            st.info("No sector data available (sector_en column may not be populated yet).")
        else:
            total_alloc = sector_raw["avg_alloc"].sum()
            sector_raw["combined_pct"] = (sector_raw["avg_alloc"] / max(total_alloc, 1) * 100).round(1)
            SECTOR_LIMIT = 35.0

            def _sector_status(pct):
                if pct > SECTOR_LIMIT:
                    return "🔴 OVER LIMIT"
                if pct > SECTOR_LIMIT * 0.85:
                    return "🟡 WARNING"
                return "🟢 OK"

            sector_raw["status"] = sector_raw["combined_pct"].apply(_sector_status)
            sector_raw = sector_raw[["sector_en", "signal_count", "combined_pct", "status"]]
            sector_raw.columns = ["Sector", "Signals (30d)", "Estimated Alloc %", "Status"]
            st.dataframe(sector_raw, use_container_width=True, hide_index=True)
            st.caption(f"Sector limit: {SECTOR_LIMIT:.0f}% — signals with status 🔴 exceed soft concentration cap.")

    except Exception as e:
        st.info(f"Sector concentration data unavailable: {e}")

    st.divider()

    # ── 6. Blocked Signals Log ────────────────────────────────────────────────
    st.subheader("🚫 Blocked Signals (last 20)")
    try:
        blocked_df = pd.read_sql(
            """SELECT ticker, action, signal_date, block_reason, raw_price,
                      expected_return, edge_ratio, regime_at_block, created_at
               FROM blocked_signals
               ORDER BY created_at DESC LIMIT 20""",
            conn_exec
        )
        if blocked_df.empty:
            st.info("No blocked signals recorded yet.")
        else:
            st.dataframe(blocked_df, use_container_width=True)
    except Exception as e:
        st.info(f"blocked_signals table not available: {e}")

    st.divider()

    # ── 7. Trailing Stop Monitor ──────────────────────────────────────────────
    st.subheader("📍 Open Position Trailing Stop Monitor")
    try:
        positions_df = pd.read_sql(
            """SELECT symbol, recommendation_date as entry_date, close_price as entry_price,
                      days_held, trailing_stop_active, trailing_stop_price, stop_loss_price,
                      target_price, realistic_fill_price, edge_ratio
               FROM trade_recommendations
               WHERE action = 'BUY'
               AND (execution_approved = 1 OR execution_approved IS NULL)
               AND actual_next_day_return IS NULL
               ORDER BY days_held DESC""",
            conn_exec
        )
        if positions_df.empty:
            st.info("No open positions tracked.")
        else:
            positions_df["trailing_active"] = positions_df["trailing_stop_active"].map(
                {0: "❌", 1: "✅", None: "—"}
            )
            positions_df["dist_to_target"] = (
                (positions_df["target_price"] - positions_df["entry_price"])
                / positions_df["entry_price"] * 100
            ).round(2)
            positions_df["dist_to_stop"] = (
                (positions_df["entry_price"] - positions_df["stop_loss_price"])
                / positions_df["entry_price"] * 100
            ).round(2)
            st.dataframe(
                positions_df[[
                    "symbol", "entry_date", "entry_price", "days_held",
                    "trailing_active", "trailing_stop_price", "stop_loss_price",
                    "target_price", "dist_to_target", "dist_to_stop", "edge_ratio"
                ]],
                use_container_width=True
            )
        conn_exec.close()
    except Exception as e:
        st.info(f"Position data not available: {e}")

st.sidebar.caption("v2.2 Financial Audit")
