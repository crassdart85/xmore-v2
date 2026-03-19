"""
Database schema and management for Trading System.

This module handles all database interactions including:
- Connection management via context managers
- Schema creation and initialization
- Data logging (prices, news, predictions, evaluations)
- Statistics and reporting
"""

import os
import sqlite3
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config import DATABASE_PATH

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use PostgreSQL on Render, SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')

# ============================================
# DATABASE CONNECTION
# ============================================

def _adapt_sql(sql):
    """Convert SQLite-style ? placeholders to PostgreSQL-style %s when using PostgreSQL."""
    if DATABASE_URL:
        return sql.replace('?', '%s')
    return sql

def _safe_add_column(cursor, table, column, col_type):
    """Add a column if it doesn't exist, handling PG transaction semantics.

    In PostgreSQL, a failed ALTER TABLE aborts the entire transaction.
    Using SAVEPOINTs lets us roll back just the failed statement.
    In SQLite, failed statements don't abort the transaction, so try/except suffices.
    """
    if DATABASE_URL:
        cursor.execute("SAVEPOINT add_col")
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            cursor.execute("RELEASE SAVEPOINT add_col")
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT add_col")
    else:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except Exception:
            pass


def _safe_create_index(cursor, sql):
    """Execute a CREATE INDEX statement safely, handling PG deadlock/concurrency.

    Multiple GH Actions jobs run create_tables() concurrently and can deadlock
    on AccessExclusiveLock. SAVEPOINTs let us roll back just the failed statement
    so the rest of create_tables() continues normally.
    """
    if DATABASE_URL:
        cursor.execute("SAVEPOINT create_idx")
        try:
            cursor.execute(sql)
            cursor.execute("RELEASE SAVEPOINT create_idx")
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT create_idx")
            logger.warning(f"Index skipped (concurrent run / deadlock): {e}")
    else:
        cursor.execute(sql)

@contextmanager
def get_connection():
    """
    Context manager for database connections.
    Uses PostgreSQL when DATABASE_URL is set (production/Render),
    falls back to SQLite locally.

    Yields:
        Connection object with dict-like row access.

    Raises:
        Exception: Rolls back transaction and re-raises any database errors.

    Example:
        >>> with get_connection() as conn:
        >>>     rows = conn.execute("SELECT * FROM prices").fetchall()
    """
    if DATABASE_URL:
        # Production: PostgreSQL
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
    else:
        # Local: SQLite
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name: row['column']

    try:
        yield conn
        conn.commit()  # Auto-commit if no errors
    except Exception as e:
        conn.rollback()  # Auto-rollback on error
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()  # Ensure connection is closed to prevent leaks

# ============================================
# SCHEMA CREATION
# ============================================

def create_tables():
    """
    Create all necessary database tables if they don't exist.

    Tables created:
    - prices: Historical stock data
    - news: Financial news articles and sentiment
    - predictions: Agent predictions
    - evaluations: Accuracy tracking of predictions
    - data_quality_log: Logs for data issues (missing data, API errors)
    - system_log: Logs for script execution runs
    """
    # Use different SQL syntax for PostgreSQL vs SQLite
    if DATABASE_URL:
        auto_id = "SERIAL PRIMARY KEY"
        bool_default = "BOOLEAN DEFAULT FALSE"
    else:
        auto_id = "INTEGER PRIMARY KEY AUTOINCREMENT"
        bool_default = "BOOLEAN DEFAULT 0"

    with get_connection() as conn:
        cursor = conn.cursor()

        # Table 1: Stock Prices
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS prices (
                id {auto_id},
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL NOT NULL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_source TEXT DEFAULT 'yahoo_finance',
                UNIQUE(symbol, date)
            )
        """)

        # Table 2: Financial News
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS news (
                id {auto_id},
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                headline TEXT NOT NULL,
                source TEXT,
                url TEXT,
                sentiment_score REAL,
                sentiment_label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, headline, date)
            )
        """)

        # Table 3: Predictions
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS predictions (
                id {auto_id},
                symbol TEXT NOT NULL,
                prediction_date DATE NOT NULL,
                target_date DATE NOT NULL,
                agent_name TEXT NOT NULL,
                prediction TEXT NOT NULL,
                confidence REAL,
                predicted_change_pct REAL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, prediction_date, target_date, agent_name)
            )
        """)

        # Table 4: Evaluations
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS evaluations (
                id {auto_id},
                prediction_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                prediction TEXT NOT NULL,
                actual_outcome TEXT,
                was_correct BOOLEAN,
                actual_change_pct REAL,
                prediction_error REAL,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id)
            )
        """)

        # Table 5: Data Quality Log
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS data_quality_log (
                id {auto_id},
                date DATE NOT NULL,
                symbol TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                description TEXT,
                severity TEXT,
                resolved {bool_default},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 6: System Log
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS system_log (
                id {auto_id},
                script_name TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                execution_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 7: Consensus Results (3-Layer Pipeline Output)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS consensus_results (
                id {auto_id},
                symbol TEXT NOT NULL,
                prediction_date DATE NOT NULL,
                
                -- Final output
                final_signal TEXT NOT NULL,
                conviction TEXT,
                confidence REAL,
                risk_adjusted {bool_default},
                
                -- Agreement
                agent_agreement REAL,
                agents_agreeing INTEGER,
                agents_total INTEGER,
                majority_direction TEXT,
                
                -- Bull / Bear scores
                bull_score INTEGER,
                bear_score INTEGER,
                
                -- Risk
                risk_action TEXT,
                risk_score INTEGER,
                
                -- Full data (JSON)
                bull_case_json TEXT,
                bear_case_json TEXT,
                risk_assessment_json TEXT,
                agent_signals_json TEXT,
                reasoning_chain_json TEXT,
                display_json TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, prediction_date)
            )
        """)

        # Add reasoning column to predictions if it doesn't exist
        _safe_add_column(cursor, "predictions", "reasoning", "TEXT")

        # Add xmore_score to consensus_results if it doesn't exist
        _safe_add_column(cursor, "consensus_results", "xmore_score", "REAL")
        _safe_add_column(cursor, "consensus_results", "calibrated_confidence", "REAL")
        _safe_add_column(cursor, "consensus_results", "expected_edge_pct", "REAL")
        _safe_add_column(cursor, "consensus_results", "ranking_score", "REAL")
        _safe_add_column(cursor, "consensus_results", "weight_profile_json", "TEXT")
        _safe_add_column(cursor, "consensus_results", "calibration_meta_json", "TEXT")

        # Table: Backtest Results (walk-forward ML performance per symbol)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id {auto_id},
                symbol TEXT NOT NULL,
                run_date DATE NOT NULL,
                n_rows INTEGER,
                n_splits INTEGER,
                accuracy REAL,
                directional_accuracy REAL,
                signal_pnl_pct REAL,
                up_precision REAL,
                down_precision REAL,
                features_used INTEGER,
                fold_scores_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, run_date)
            )
        """)

        # Table 8: Users (Auth)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                id {auto_id},
                email TEXT NOT NULL,
                email_lower TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                preferred_language TEXT DEFAULT 'en',
                is_active {bool_default},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP
            )
        """)

        # Table 9: EGX 30 Stocks Reference
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS egx30_stocks (
                id {auto_id},
                symbol TEXT NOT NULL UNIQUE,
                name_en TEXT NOT NULL,
                name_ar TEXT NOT NULL,
                sector_en TEXT,
                sector_ar TEXT,
                is_active {bool_default},
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 10: User Watchlist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS user_watchlist (
                id {auto_id},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                stock_id INTEGER NOT NULL REFERENCES egx30_stocks(id) ON DELETE CASCADE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, stock_id)
            )
        """)

        # Table 12: User Positions (Virtual Portfolio)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS user_positions (
                id {auto_id},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                entry_date DATE NOT NULL,
                entry_price REAL,
                exit_date DATE,
                exit_price REAL,
                return_pct REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Partial index for unique OPEN position
        _safe_create_index(cursor, "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_position ON user_positions(user_id, symbol) WHERE status = 'OPEN'")

        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_positions_user ON user_positions(user_id)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_positions_status ON user_positions(status)")

        # Table 13: Trade Recommendations
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS trade_recommendations (
                id {auto_id},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                symbol TEXT NOT NULL,
                recommendation_date DATE NOT NULL,
                
                action TEXT NOT NULL,
                signal TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                conviction TEXT,
                risk_action TEXT,
                priority REAL,
                
                close_price REAL,
                stop_loss_pct REAL,
                target_pct REAL,
                stop_loss_price REAL,
                target_price REAL,
                risk_reward_ratio REAL,
                
                reasons TEXT,
                reasons_ar TEXT,
                
                bull_score INTEGER,
                bear_score INTEGER,
                agents_agreeing INTEGER,
                agents_total INTEGER,
                risk_flags TEXT,
                
                actual_next_day_return REAL,
                actual_5day_return REAL,
                was_correct {bool_default},
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(user_id, symbol, recommendation_date)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_trade_rec_user_date ON trade_recommendations(user_id, recommendation_date DESC)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_trade_rec_date ON trade_recommendations(recommendation_date DESC)")

        # Table 14: Daily Briefings (one global row per date)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_briefings (
                id {auto_id},
                briefing_date DATE NOT NULL UNIQUE,
                market_pulse_json TEXT,
                sector_breakdown_json TEXT,
                risk_alerts_json TEXT,
                sentiment_snapshot_json TEXT,
                stocks_processed INTEGER,
                generation_time_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_briefings_date ON daily_briefings(briefing_date DESC)")

        # Table 11: Sentiment Scores (Aggregated)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS sentiment_scores (
                id {auto_id},
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                avg_sentiment REAL,
                sentiment_label TEXT,
                article_count INTEGER DEFAULT 0,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_date ON sentiment_scores(symbol, date)")

        # Table 15: Prediction Audit Log (track changes for transparency)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS prediction_audit_log (
                id {auto_id},
                table_name TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                field_changed TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON prediction_audit_log(changed_at DESC)")

        # Table 16: Agent Performance Daily (per-agent accuracy snapshots)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS agent_performance_daily (
                id {auto_id},
                snapshot_date DATE NOT NULL,
                agent_name TEXT NOT NULL,
                win_rate_30d REAL,
                win_rate_90d REAL,
                predictions_30d INTEGER DEFAULT 0,
                predictions_90d INTEGER DEFAULT 0,
                avg_confidence_30d REAL,
                avg_confidence_90d REAL,
                avg_alpha_30d REAL,
                avg_alpha_90d REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_date, agent_name)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_agent_perf_date ON agent_performance_daily(snapshot_date DESC)")

        # Add missing columns to agent_performance_daily (correct_30d/90d were absent from original schema)
        agent_perf_columns = [
            ("correct_30d", "INTEGER DEFAULT 0"),
            ("correct_90d", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in agent_perf_columns:
            _safe_add_column(cursor, "agent_performance_daily", col_name, col_type)

        # Market regime log (written by run_agents.py after HMM detection)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS regime_log (
                id {auto_id},
                date DATE NOT NULL UNIQUE,
                regime TEXT NOT NULL,
                hmm_state INTEGER,
                volatility REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_regime_log_date ON regime_log(date DESC)")

        # Add benchmark columns to trade_recommendations (safe ALTER TABLE)
        benchmark_columns = [
            ("benchmark_1d_return", "REAL"),
            ("alpha_1d", "REAL"),
            ("benchmark_5d_return", "REAL"),
            ("alpha_5d", "REAL"),
            ("is_live", f"{bool_default}"),
        ]
        for col_name, col_type in benchmark_columns:
            _safe_add_column(cursor, "trade_recommendations", col_name, col_type)

        # Add session-sheet columns (pivot levels, trend, buy guide, rec type, patterns)
        session_columns = [
            ("trend_ar",    "TEXT"),
            ("trend_en",    "TEXT"),
            ("rec_type_ar", "TEXT"),
            ("rec_type_en", "TEXT"),
            ("buy_guide",   "REAL"),
            ("pivot",       "REAL"),
            ("r1",          "REAL"),
            ("r2",          "REAL"),
            ("s1",          "REAL"),
            ("s2",          "REAL"),
            ("patterns",    "TEXT"),
        ]
        for col_name, col_type in session_columns:
            _safe_add_column(cursor, "trade_recommendations", col_name, col_type)

        execution_columns = [
            ("realistic_fill_price", "REAL"),
            ("position_value_egp", "REAL"),
            ("round_trip_cost_egp", "REAL"),
            ("edge_ratio", "REAL"),
            ("split_required", f"{bool_default}"),
            ("realistic_stop_price", "REAL"),
            ("execution_approved", f"{bool_default}"),
            ("volatility_position_pct", "REAL"),
            ("kelly_position_pct", "REAL"),
            ("position_size_pct", "REAL"),
            ("shares_requested", "INTEGER"),
            ("shares_expected", "INTEGER"),
            ("position_sizing_mode", "TEXT"),
        ]
        for col_name, col_type in execution_columns:
            _safe_add_column(cursor, "trade_recommendations", col_name, col_type)

        # Add benchmark + quantity columns to user_positions
        position_columns = [
            ("benchmark_return_pct", "REAL"),
            ("alpha_pct", "REAL"),
            ("quantity", "INTEGER DEFAULT 1"),
        ]
        for col_name, col_type in position_columns:
            _safe_add_column(cursor, "user_positions", col_name, col_type)

        # Add horizon_days to evaluations (for D+5/D+10/D+20 tracking)
        _safe_add_column(cursor, "evaluations", "horizon_days", "INTEGER DEFAULT 5")

        # Table 36: Price Alerts
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id          {auto_id},
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                symbol      TEXT NOT NULL,
                condition   TEXT NOT NULL DEFAULT 'above',
                target_price REAL NOT NULL,
                active      {bool_default},
                triggered_at TIMESTAMP,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_alerts_user ON price_alerts(user_id)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_alerts_active ON price_alerts(active)")

        # Table 37: FX Rates History (one row per day)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS fx_rates_history (
                id              {auto_id},
                date            DATE NOT NULL UNIQUE,
                usd_egp         REAL,
                usd_sar         REAL,
                xau_usd         REAL,
                gold_24k_egp_g  REAL,
                gold_21k_egp_g  REAL,
                gold_pound_egp  REAL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_fx_history_date ON fx_rates_history(date DESC)")

        # Table 38: Stock Signal Evaluations at multiple horizons (D+5, D+10, D+20)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS stock_signal_evals (
                id               {auto_id},
                symbol           TEXT NOT NULL,
                prediction_date  DATE NOT NULL,
                horizon_days     INTEGER NOT NULL,
                predicted_signal TEXT,
                actual_change_pct REAL,
                was_correct      {bool_default},
                evaluated_at     DATE DEFAULT CURRENT_DATE,
                UNIQUE(symbol, prediction_date, horizon_days)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_sse_symbol ON stock_signal_evals(symbol, prediction_date DESC)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_sse_horizon ON stock_signal_evals(horizon_days)")

        # Seed EGX 30 stocks (upsert: ignore if already exists)
        egx30_stocks = [
            ('COMI.CA', 'Commercial International Bank', 'البنك التجاري الدولي', 'Banking', 'البنوك'),
            ('HRHO.CA', 'Hermes Holding', 'القابضة المصرية الكويتية (هيرميس)', 'Financial Services', 'الخدمات المالية'),
            ('TMGH.CA', 'Talaat Moustafa Group', 'مجموعة طلعت مصطفى', 'Real Estate', 'العقارات'),
            ('SWDY.CA', 'Elsewedy Electric', 'السويدي إليكتريك', 'Industrials', 'الصناعات'),
            ('EAST.CA', 'Eastern Company', 'الشرقية (إيسترن كومباني)', 'Consumer Staples', 'السلع الأساسية'),
            ('ETEL.CA', 'Telecom Egypt', 'المصرية للاتصالات', 'Telecom', 'الاتصالات'),
            ('ABUK.CA', 'Abu Qir Fertilizers', 'أبو قير للأسمدة', 'Materials', 'المواد'),
            ('ORWE.CA', 'Oriental Weavers', 'السجاد الشرقية (أوريانتال ويفرز)', 'Consumer Discretionary', 'السلع الاستهلاكية'),
            ('EFIH.CA', 'EFG Hermes', 'إي إف جي هيرميس', 'Financial Services', 'الخدمات المالية'),
            ('OCDI.CA', 'Orascom Development', 'أوراسكوم للتنمية', 'Real Estate', 'العقارات'),
            ('PHDC.CA', 'Palm Hills Development', 'بالم هيلز للتعمير', 'Real Estate', 'العقارات'),
            ('MNHD.CA', 'Madinet Nasr Housing', 'مدينة نصر للإسكان', 'Real Estate', 'العقارات'),
            ('CLHO.CA', 'Cleopatra Hospital', 'مستشفى كليوباترا', 'Healthcare', 'الرعاية الصحية'),
            ('EKHO.CA', 'Ezz Steel', 'حديد عز', 'Materials', 'المواد'),
            ('AMOC.CA', 'Alexandria Mineral Oils', 'الإسكندرية للزيوت المعدنية', 'Energy', 'الطاقة'),
            ('ESRS.CA', 'Ezz Steel (Rebars)', 'عز الدخيلة للصلب', 'Materials', 'المواد'),
            ('HELI.CA', 'Heliopolis Housing', 'مصر الجديدة للإسكان', 'Real Estate', 'العقارات'),
            ('GBCO.CA', 'GB Auto', 'جي بي أوتو', 'Consumer Discretionary', 'السلع الاستهلاكية'),
            ('CCAP.CA', 'Citadel Capital (Qalaa)', 'القلعة (سيتاديل كابيتال)', 'Financial Services', 'الخدمات المالية'),
            ('JUFO.CA', 'Juhayna Food', 'جهينة', 'Consumer Staples', 'السلع الأساسية'),
            ('SKPC.CA', 'Sidi Kerir Petrochemicals', 'سيدي كرير للبتروكيماويات', 'Materials', 'المواد'),
            ('ORAS.CA', 'Orascom Construction', 'أوراسكوم للإنشاءات', 'Industrials', 'الصناعات'),
            ('FWRY.CA', 'Fawry', 'فوري', 'Technology', 'التكنولوجيا'),
            ('EKHOA.CA', 'Ezz Aldekhela', 'عز الدخيلة', 'Materials', 'المواد'),
            ('BINV.CA', 'Beltone Financial', 'بلتون المالية القابضة', 'Financial Services', 'الخدمات المالية'),
            ('EIOD.CA', 'E-Finance', 'إي فاينانس', 'Technology', 'التكنولوجيا'),
            ('TALM.CA', 'Talem Medical', 'تاليم الطبية', 'Healthcare', 'الرعاية الصحية'),
            ('ADIB.CA', 'Abu Dhabi Islamic Bank Egypt', 'مصرف أبوظبي الإسلامي – مصر', 'Banking', 'البنوك'),
            ('DMCR.CA', 'Dice Medical & Scientific', 'دايس الطبية والعلمية', 'Healthcare', 'الرعاية الصحية'),
            ('ASCM.CA', 'Arabian Cement', 'الأسمنت العربية', 'Materials', 'المواد'),
        ]
        if DATABASE_URL:
            for stock in egx30_stocks:
                cursor.execute(_adapt_sql("""
                    INSERT INTO egx30_stocks (symbol, name_en, name_ar, sector_en, sector_ar)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (symbol) DO NOTHING
                """), stock)
        else:
            for stock in egx30_stocks:
                cursor.execute("""
                    INSERT OR IGNORE INTO egx30_stocks (symbol, name_en, name_ar, sector_en, sector_ar)
                    VALUES (?, ?, ?, ?, ?)
                """, stock)

        # Table 17: Forecast Portfolios (user-defined stock lists for recurring forecasts)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS forecast_portfolios (
                id {auto_id},
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                symbols_json TEXT NOT NULL DEFAULT '[]',
                horizon_days INTEGER NOT NULL DEFAULT 63,
                scenario TEXT NOT NULL DEFAULT 'base',
                investment_amount REAL NOT NULL DEFAULT 10000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_fp_user ON forecast_portfolios(user_id)")

        # Table 18: Portfolio Forecast Results (one row per stock per run)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS portfolio_forecast_results (
                id {auto_id},
                portfolio_id INTEGER NOT NULL REFERENCES forecast_portfolios(id) ON DELETE CASCADE,
                symbol TEXT NOT NULL,
                run_date DATE NOT NULL,
                target_date DATE NOT NULL,
                horizon_days INTEGER NOT NULL,
                scenario TEXT NOT NULL DEFAULT 'base',
                investment_amount REAL,
                expected_return_pct REAL,
                probability_positive REAL,
                worst_case_pct REAL,
                median_pct REAL,
                best_case_pct REAL,
                volatility_annual_pct REAL,
                data_points INTEGER,
                ok {bool_default},
                error_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portfolio_id, symbol, run_date, horizon_days, scenario)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pfr_portfolio ON portfolio_forecast_results(portfolio_id, run_date DESC)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pfr_target ON portfolio_forecast_results(target_date)")

        # Table 19: Portfolio Forecast Evaluations (actual vs forecasted, auto-filled by evaluate.py)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS portfolio_forecast_evaluations (
                id {auto_id},
                forecast_result_id INTEGER NOT NULL REFERENCES portfolio_forecast_results(id) ON DELETE CASCADE,
                portfolio_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                run_date DATE NOT NULL,
                target_date DATE NOT NULL,
                expected_return_pct REAL,
                actual_return_pct REAL,
                actual_close REAL,
                error_pct REAL,
                within_5pct {bool_default},
                within_10pct {bool_default},
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(forecast_result_id)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pfe_portfolio ON portfolio_forecast_evaluations(portfolio_id)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pfe_symbol ON portfolio_forecast_evaluations(symbol)")

        # Table 20: Portfolio Daily Actuals (actual price recorded each day for in-progress forecasts)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS portfolio_daily_actuals (
                id {auto_id},
                portfolio_id INTEGER NOT NULL REFERENCES forecast_portfolios(id) ON DELETE CASCADE,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                actual_close REAL NOT NULL,
                return_pct_from_start REAL,
                UNIQUE(portfolio_id, symbol, date)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pda_portfolio ON portfolio_daily_actuals(portfolio_id, date DESC)")

        # Table 21: Market Reports (PDF/image knowledge base, uploaded via Admin)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS market_reports (
                id           {auto_id},
                filename     TEXT NOT NULL,
                upload_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                extracted_text TEXT,
                language     TEXT NOT NULL DEFAULT 'EN',
                summary      TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_market_reports_upload_date ON market_reports(upload_date DESC)")

        # Table 22: RAG Chunks (embedded text from market_reports, news, event_intel)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id          {auto_id},
                source_type TEXT NOT NULL DEFAULT 'market_report',
                source_id   INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text  TEXT NOT NULL,
                embedding   TEXT,
                source_meta TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_type, source_id, chunk_index)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source_type, source_id)")
        # Add source_meta to existing installs that predate this column
        _safe_add_column(cursor, 'rag_chunks', 'source_meta', 'TEXT')

        # Table 23: Prediction Contexts (snapshot + embedding + outcome for pattern matching)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS prediction_contexts (
                id                {auto_id},
                symbol            TEXT NOT NULL,
                prediction_date   DATE NOT NULL,
                context_json      TEXT NOT NULL,
                embedding         TEXT,
                actual_outcome    TEXT,
                actual_change_pct REAL,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, prediction_date)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pc_symbol ON prediction_contexts(symbol, prediction_date DESC)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_pc_outcome ON prediction_contexts(actual_outcome)")

        # ── ETF / Instrument tables (Tables 24–35) ──────────────────────────────

        # Table 24: Instrument master (ETFs, equities — local EGX + global)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS instrument (
                id               {auto_id},
                type             TEXT NOT NULL DEFAULT 'ETF',
                region           TEXT,
                symbol           TEXT NOT NULL,
                isin             TEXT,
                name             TEXT,
                exchange         TEXT,
                currency         TEXT,
                country          TEXT,
                issuer           TEXT,
                underlying_index TEXT,
                inception_date   DATE,
                is_active        INTEGER NOT NULL DEFAULT 1,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(exchange, symbol)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_instrument_symbol ON instrument(symbol)")

        # Table 25: Instrument aliases (AR/EN name variants, ticker variants)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS instrument_alias (
                id            {auto_id},
                instrument_id INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                alias         TEXT NOT NULL,
                alias_type    TEXT NOT NULL DEFAULT 'GENERAL',
                UNIQUE(instrument_id, alias)
            )
        """)

        # Table 26: ETF daily trading tape (OHLCV + trades + market cap)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_price_daily (
                instrument_id INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                trade_date    DATE NOT NULL,
                open_price    REAL,
                high_price    REAL,
                low_price     REAL,
                close_price   REAL,
                last_price    REAL,
                pct_change    REAL,
                value_traded  REAL,
                volume        REAL,
                trades        INTEGER,
                market_cap_mn REAL,
                source_url    TEXT NOT NULL,
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, trade_date)
            )
        """)

        # Table 27: ETF NAV per unit
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_nav (
                instrument_id   INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                nav_date        DATE NOT NULL,
                nav_value       REAL NOT NULL,
                last_update_raw TEXT,
                source_url      TEXT NOT NULL,
                ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, nav_date)
            )
        """)

        # Table 28: ETF intraday NAV + tracking error
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_inav (
                instrument_id  INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                ts             TIMESTAMP NOT NULL,
                inav_value     REAL,
                tracking_error REAL,
                source_url     TEXT NOT NULL,
                ingested_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, ts)
            )
        """)

        # Table 29: ETF premium/discount (computed: market price vs NAV)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_premium_discount_daily (
                instrument_id    INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                asof_date        DATE NOT NULL,
                market_price     REAL NOT NULL,
                nav_value        REAL NOT NULL,
                premium_discount REAL NOT NULL,
                nav_date_used    DATE NOT NULL,
                calc_notes       TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, asof_date)
            )
        """)

        # Table 30: ETF fund volume (AUM proxy: fund size, net subs, units)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_fund_volume (
                instrument_id   INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                asof_date       DATE NOT NULL,
                fund_size       REAL,
                net_subs        REAL,
                no_units        REAL,
                last_update_raw TEXT,
                source_url      TEXT NOT NULL,
                ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, asof_date)
            )
        """)

        # Table 31: ETF holdings snapshot header
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_holdings_snapshot (
                id            {auto_id},
                instrument_id INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                snapshot_date DATE NOT NULL,
                source        TEXT NOT NULL,
                source_url    TEXT NOT NULL,
                currency      TEXT,
                total_weight  REAL,
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(instrument_id, snapshot_date, source)
            )
        """)

        # Table 32: ETF holding lines (constituents + weights)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_holding_line (
                snapshot_id    INTEGER NOT NULL REFERENCES etf_holdings_snapshot(id) ON DELETE CASCADE,
                line_no        INTEGER NOT NULL,
                holding_symbol TEXT,
                holding_name   TEXT NOT NULL,
                holding_isin   TEXT,
                weight_pct     REAL NOT NULL,
                country        TEXT,
                sector         TEXT,
                asset_type     TEXT,
                PRIMARY KEY (snapshot_id, line_no)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_holding_line_symbol ON etf_holding_line(holding_symbol)")

        # Table 33: ETF country exposure (for global ETFs: Egypt weight, etc.)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS etf_country_exposure (
                instrument_id INTEGER NOT NULL REFERENCES instrument(id) ON DELETE CASCADE,
                asof_date     DATE NOT NULL,
                country       TEXT NOT NULL,
                weight_pct    REAL NOT NULL,
                source_url    TEXT NOT NULL,
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (instrument_id, asof_date, country)
            )
        """)

        # Table 34: RAG document metadata (PDFs: prospectuses, factsheets, info sheets)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS rag_document (
                id            {auto_id},
                instrument_id INTEGER REFERENCES instrument(id) ON DELETE SET NULL,
                doc_type      TEXT NOT NULL,
                title         TEXT NOT NULL,
                publisher     TEXT,
                language      TEXT,
                publish_date  DATE,
                url           TEXT NOT NULL,
                content_hash  TEXT,
                storage_uri   TEXT,
                fetched_at    TIMESTAMP,
                ingested_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            )
        """)

        # Table 35: RAG embedding job queue
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS rag_embedding_job (
                id            {auto_id},
                doc_id        INTEGER NOT NULL REFERENCES rag_document(id) ON DELETE CASCADE,
                embed_model   TEXT NOT NULL DEFAULT 'text-embedding-005',
                status        TEXT NOT NULL DEFAULT 'PENDING',
                started_at    TIMESTAMP,
                finished_at   TIMESTAMP,
                error_message TEXT
            )
        """)

        # Table 36: Universal Investor Scoring — scored_signals
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS scored_signals (
                id               {auto_id},
                symbol           TEXT NOT NULL,
                signal_date      DATE NOT NULL,
                action           TEXT NOT NULL DEFAULT 'HOLD',
                composite_score  REAL NOT NULL,
                scoring_mode     TEXT NOT NULL DEFAULT 'standard_100',
                score_value      TEXT NOT NULL,
                consensus_score  REAL,
                execution_score  REAL,
                regime_score     REAL,
                momentum_score   REAL,
                meets_threshold  BOOLEAN DEFAULT FALSE,
                all_formats      TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, signal_date)
            )
        """)

        # Table 37: Daily Top Picks (best 5 stocks per day, upserted idempotently)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_top_picks (
                id              {auto_id},
                pick_date       DATE NOT NULL,
                rank            INTEGER NOT NULL,
                symbol          TEXT NOT NULL,
                consensus_signal TEXT,
                conviction      TEXT,
                sentiment_score REAL,
                weighted_score  REAL,
                entry_price     REAL,
                target_price    REAL,
                rationale       TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pick_date, rank)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_top_picks_date ON daily_top_picks(pick_date DESC)")

        # Table 38: Daily Sector Rotation (top sectors by buy signal strength)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS daily_sector_rotation (
                id                    {auto_id},
                rotation_date         DATE NOT NULL,
                sector                TEXT NOT NULL,
                buy_signal_count      INTEGER DEFAULT 0,
                avg_conviction        REAL,
                volatility_20d        REAL,
                composite_score       REAL,
                rank                  INTEGER,
                recommended_allocation REAL,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(rotation_date, sector)
            )
        """)
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_sector_rotation_date ON daily_sector_rotation(rotation_date DESC)")

        # Add momentum_alignment column to consensus_results (safe for existing installs)
        _safe_add_column(cursor, "consensus_results", "momentum_alignment", "REAL DEFAULT 50")

        # Create indexes for common queries
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news(symbol, date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol, prediction_date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_consensus_symbol ON consensus_results(symbol, prediction_date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_consensus_date ON consensus_results(prediction_date)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users(email_lower)")
        _safe_create_index(cursor, "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id)")

        logger.info("✅ Database tables created successfully")

# ============================================
# HELPER FUNCTIONS
# ============================================

def log_data_quality_issue(symbol: str, issue_type: str, description: str, severity: str = 'medium'):
    """
    Log data quality issues to the database.
    
    Args:
        symbol (str): Stock symbol related to the issue.
        issue_type (str): Category of issue (e.g., 'missing_data', 'api_failure').
        description (str): Detailed description of the problem.
        severity (str): 'low', 'medium', or 'high'. Defaults to 'medium'.
    
    Example:
        >>> log_data_quality_issue('AAPL', 'missing_data', 'No close price for 2023-10-25')
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql("""
            INSERT INTO data_quality_log (date, symbol, issue_type, description, severity)
            VALUES (CURRENT_DATE, ?, ?, ?, ?)
        """), (symbol, issue_type, description, severity))
        logger.warning(f"⚠️  Data quality issue logged: {symbol} - {issue_type}")

def log_system_run(script_name: str, status: str, message: str = None, execution_time: float = None):
    """
    Log global script execution status.
    
    Args:
        script_name (str): Name of the script being run (e.g., 'collect_data.py').
        status (str): Outcome of the run ('success', 'failure', 'partial').
        message (str, optional): Additional details or error message.
        execution_time (float, optional): Runtime duration in seconds.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql("""
            INSERT INTO system_log (script_name, status, message, execution_time_seconds)
            VALUES (?, ?, ?, ?)
        """), (script_name, status, message, execution_time))

def get_latest_price_date(symbol: str) -> Optional[str]:
    """
    Get the most recent date for which we have price data for a symbol.
    
    Args:
        symbol (str): Stock symbol to query.
        
    Returns:
        Optional[str]: Date string (YYYY-MM-DD) or None if no data exists.
        
    Example:
        >>> latest = get_latest_price_date('MSFT')
        >>> print(latest)
        '2023-10-27'
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql("""
            SELECT MAX(date) as latest_date
            FROM prices
            WHERE symbol = ?
        """), (symbol,))
        result = cursor.fetchone()
        return result['latest_date'] if result else None

def check_missing_data(symbol: str, start_date: str, end_date: str) -> List[str]:
    """
    Check for missing dates in price data within a range.
    
    Args:
        symbol (str): Stock symbol to check.
        start_date (str): Start of range (YYYY-MM-DD).
        end_date (str): End of range (YYYY-MM-DD).
        
    Returns:
        List[str]: List of dates that exist in the database for this range.
        
    Note:
        Logs a warning if more than 30% of expected days are missing.
        
    Example:
        >>> dates = check_missing_data('GOOGL', '2023-01-01', '2023-01-31')
        >>> if len(dates) < 20: print("Data gaps detected")
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql("""
            SELECT date FROM prices
            WHERE symbol = ? AND date BETWEEN ? AND ?
            ORDER BY date
        """), (symbol, start_date, end_date))

        dates = [row['date'] for row in cursor.fetchall()]
        
        # Simple check: count business days vs actual days
        # (More sophisticated version would exclude weekends/holidays)
        expected_days = (datetime.fromisoformat(end_date) - datetime.fromisoformat(start_date)).days
        actual_days = len(dates)
        
        if actual_days < expected_days * 0.7:  # Missing more than 30% of days
            logger.warning(f"⚠️  {symbol}: Only {actual_days}/{expected_days} days of data")
        
        return dates

def get_recent_prices(symbol: str, days: int = 60) -> List[Dict[str, Any]]:
    """
    Get recent price data for a symbol.
    
    Args:
        symbol (str): Stock symbol.
        days (int): Number of recent records to retrieve. Defaults to 60.
        
    Returns:
        List[Dict[str, Any]]: List of price records (dictionaries).
        
    Example:
        >>> prices = get_recent_prices('AAPL', days=5)
        >>> print(prices[0]['close'])
        175.50
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql("""
            SELECT * FROM prices
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
        """), (symbol, days))

        return [dict(row) for row in cursor.fetchall()]

def get_statistics() -> Dict[str, Any]:
    """
    Get comprehensive database statistics.
    
    Returns:
        Dict[str, Any]: Dictionary containing counts of prices, news, predictions,
                       evaluations, stocks tracked, date ranges, and recent issues.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        
        # Count records in each table
        cursor.execute("SELECT COUNT(*) as count FROM prices")
        stats['total_prices'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM news")
        stats['total_news'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM predictions")
        stats['total_predictions'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM evaluations")
        stats['total_evaluations'] = cursor.fetchone()['count']
        
        # Count stocks being tracked
        cursor.execute("SELECT COUNT(DISTINCT symbol) as count FROM prices")
        stats['stocks_tracked'] = cursor.fetchone()['count']
        
        # Date range
        cursor.execute("SELECT MIN(date) as earliest, MAX(date) as latest FROM prices")
        date_range = cursor.fetchone()
        stats['earliest_date'] = date_range['earliest']
        stats['latest_date'] = date_range['latest']
        
        # Recent data quality issues
        if DATABASE_URL:
            date_expr = "CURRENT_DATE - INTERVAL '7 days'"
        else:
            date_expr = "DATE('now', '-7 days')"
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM data_quality_log
            WHERE date >= {date_expr} AND resolved = 0
        """)
        stats['recent_issues'] = cursor.fetchone()['count']
        
        return stats

# ============================================
# DATABASE INITIALIZATION
# ============================================

def initialize_database():
    """
    Initialize the database by creating tables and printing current statistics.
    Useful to run on first setup or to verify database state.
    """
    logger.info("🔧 Initializing database...")
    create_tables()
    
    # Display stats if database already has data
    stats = get_statistics()
    if stats['total_prices'] > 0:
        logger.info(f"📊 Database contains:")
        logger.info(f"   - {stats['total_prices']} price records")
        logger.info(f"   - {stats['total_news']} news articles")
        logger.info(f"   - {stats['total_predictions']} predictions")
        logger.info(f"   - {stats['stocks_tracked']} stocks tracked")
        logger.info(f"   - Date range: {stats['earliest_date']} to {stats['latest_date']}")
        
        if stats['recent_issues'] > 0:
            logger.warning(f"⚠️  {stats['recent_issues']} unresolved data quality issues in last 7 days")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    # When run directly, initialize database and show stats
    initialize_database()
    
    print("\n" + "="*60)
    print("Database initialized successfully!")
    print("="*60)
    
    stats = get_statistics()
    print(f"\n📊 Current Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
