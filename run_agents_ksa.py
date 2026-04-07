"""
KSA/Tadawul Daily Signal Orchestrator — Xmore.

Flow:
  1. Holiday check (Saudi national holidays 2026)
  2. Connect to PostgreSQL via DATABASE_URL
  3. Run KSA intelligence layer (material tickers)
  4. Run KSA Telegram reader
  5. Detect TASI market regime (20-day MA classification)
  6. Fetch 6-month price history per ticker via yfinance
  7. Run 5 agents per ticker (MA, RSI, Volume, ML, Gemini)
  8. Run consensus engine -> write to trade_recommendations with market_id='KSA'
  9. Publish approved signals to WhatsApp

All log lines are prefixed with [KSA].

CLI:
  python run_agents_ksa.py                  -- full run (all universe tickers)
  python run_agents_ksa.py --dry-run        -- skip DB writes and WhatsApp
  python run_agents_ksa.py --ticker 2222.SR -- single ticker
  python run_agents_ksa.py --force-run      -- bypass holiday/weekend guard
"""

import os
import json
import logging
import argparse
import datetime
import traceback

import numpy as np
import pandas as pd
import psycopg2
import yfinance as yf

# ---------------------------------------------------------------------------
# Config imports (from existing Xmore config layer)
# ---------------------------------------------------------------------------
try:
    from config.execution_config import TADAWUL_CONFIG
except Exception as _cfg_err:
    TADAWUL_CONFIG = {}
    print(f"[KSA] WARNING: Could not import TADAWUL_CONFIG: {_cfg_err}")

try:
    from config.ksa_universe import KSA_TOP50, KSA_INITIAL_UNIVERSE
except Exception as _uni_err:
    KSA_TOP50 = []
    KSA_INITIAL_UNIVERSE = []
    print(f"[KSA] WARNING: Could not import KSA universe: {_uni_err}")

try:
    from config.ksa_holidays import SAUDI_HOLIDAYS, is_trading_day, is_saudi_holiday
except Exception as _hol_err:
    SAUDI_HOLIDAYS = set()
    print(f"[KSA] WARNING: Could not import KSA holidays: {_hol_err}")

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MARKET_ID   = "KSA"
TASI_TICKER = "^TASI.SR"
_TABLE_COLUMNS_CACHE: dict[str, set[str]] = {}

# Saudi holidays imported from config.ksa_holidays (shared module).
# Retained as local alias for backward compatibility with inline references.
SAUDI_HOLIDAYS_2026 = list(SAUDI_HOLIDAYS)

# Tadawul trading week: Sunday-Thursday (weekday indices Sun=6, Mon=0 ... Thu=3)
_TADAWUL_TRADING_DAYS = {6, 0, 1, 2, 3}


def _get_table_columns(conn, table_name: str) -> set[str]:
    """Return lowercase column names for a table using the current DB backend."""
    cache_key = table_name.lower()
    if cache_key in _TABLE_COLUMNS_CACHE:
        return _TABLE_COLUMNS_CACHE[cache_key]

    cursor = conn.cursor()
    cols: set[str] = set()
    try:
        if hasattr(conn, "server_version"):
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table_name,),
            )
            cols = {str(row[0]).lower() for row in cursor.fetchall()}
        else:
            cursor.execute(f"PRAGMA table_info({table_name})")
            cols = {str(row[1]).lower() for row in cursor.fetchall()}
    except Exception as exc:
        logger.debug(f"[KSA] Could not inspect columns for {table_name}: {exc}")

    _TABLE_COLUMNS_CACHE[cache_key] = cols
    return cols


# ---------------------------------------------------------------------------
# Holiday / trading-day helpers
# ---------------------------------------------------------------------------

def is_holiday(check_date: datetime.date = None) -> bool:
    """
    Return True if check_date (default today) is a Saudi public holiday or
    falls on the Tadawul weekend (Friday or Saturday).
    Delegates to shared config.ksa_holidays module.
    """
    if check_date is None:
        check_date = datetime.date.today()
    return not is_trading_day(check_date)


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------

def _detect_market_regime(conn) -> dict:
    """
    Download last ~30 trading days of TASI data via yfinance.
    Compute 20-day MA and classify current market regime.

    Turbulent conditions: price > 3% below MA20 OR 20-day vol > 2.5%.
    Otherwise: Calm.

    Returns dict:
        {
            "label":      "Calm" | "Turbulent",
            "is_bearish": bool,
            "tasi_price": float,
            "ma20":       float,
            "vol_20d":    float
        }

    Writes to regime_log table with market_id='KSA'. Non-fatal on any error.
    """
    default_regime: dict = {
        "label":      "Calm",
        "is_bearish": False,
        "tasi_price": None,
        "ma20":       None,
        "vol_20d":    None,
    }
    try:
        tasi_raw = yf.download(
            TASI_TICKER,
            period="2mo",
            auto_adjust=True,
            progress=False,
        )
        if tasi_raw is None or len(tasi_raw) < 20:
            logger.warning(
                "[KSA] Regime detection: insufficient TASI data -- defaulting to Calm"
            )
            return default_regime

        tasi_df = tasi_raw.reset_index()

        # Flatten multi-level column index produced by yfinance >= 0.2
        if isinstance(tasi_df.columns, pd.MultiIndex):
            tasi_df.columns = [
                c[0].lower() if isinstance(c, tuple) else c.lower()
                for c in tasi_df.columns
            ]
        else:
            tasi_df.columns = [c.lower() for c in tasi_df.columns]

        close_col = "close" if "close" in tasi_df.columns else "adj close"
        closes = tasi_df[close_col].dropna()

        if len(closes) < 20:
            logger.warning(
                "[KSA] Regime detection: fewer than 20 valid closes -- defaulting to Calm"
            )
            return default_regime

        ma20        = float(closes.tail(20).mean())
        tasi_price  = float(closes.iloc[-1])
        is_bearish  = tasi_price < ma20

        returns     = closes.pct_change().dropna().tail(20)
        vol_20d     = float(returns.std()) if len(returns) >= 5 else 0.0

        # Turbulent: bearish AND (> 3% below MA or vol > 2.5%)
        is_turbulent = is_bearish and (
            (tasi_price / ma20 - 1.0) < -0.03 or vol_20d > 0.025
        )
        label = "Turbulent" if is_turbulent else "Calm"

        regime: dict = {
            "label":      label,
            "is_bearish": is_bearish,
            "tasi_price": tasi_price,
            "ma20":       ma20,
            "vol_20d":    vol_20d,
        }

        # Persist to regime_log (best-effort; table may not exist on all envs)
        try:
            cols = _get_table_columns(conn, "regime_log")
            payload = {}
            if "date" in cols:
                payload["date"] = datetime.date.today()
            if "market_id" in cols:
                payload["market_id"] = MARKET_ID
            if "regime_label" in cols:
                payload["regime_label"] = label
            if "regime_label_en" in cols:
                payload["regime_label_en"] = label
            if "regime_label_ar" in cols:
                payload["regime_label_ar"] = "هادئ" if label == "Calm" else "متقلب"
            if "regime_confidence" in cols:
                payload["regime_confidence"] = 0.70
            if "current_regime" in cols:
                payload["current_regime"] = 0 if label == "Calm" else 1
            if "n_regimes" in cols:
                payload["n_regimes"] = 2
            if "regime" in cols:
                payload["regime"] = label
            if "hmm_state" in cols:
                payload["hmm_state"] = 0 if label == "Calm" else 1
            if "volatility" in cols:
                payload["volatility"] = vol_20d
            if "is_bearish" in cols:
                payload["is_bearish"] = is_bearish
            if "index_price" in cols:
                payload["index_price"] = tasi_price
            if "ma20" in cols:
                payload["ma20"] = ma20
            if "detected_at" in cols:
                payload["detected_at"] = datetime.datetime.utcnow()

            if payload:
                col_names = list(payload.keys())
                placeholders = ", ".join(["%s"] * len(col_names))
                columns_sql = ", ".join(col_names)
                cursor = conn.cursor()
                cursor.execute(
                    f"INSERT INTO regime_log ({columns_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    [payload[c] for c in col_names],
                )
                conn.commit()
        except Exception as _db_err:
            logger.debug(f"[KSA] regime_log write skipped: {_db_err}")
            try:
                conn.rollback()
            except Exception:
                pass

        logger.info(
            f"[KSA] Regime: {label} | TASI={tasi_price:.2f} "
            f"MA20={ma20:.2f} vol_20d={vol_20d:.4f} bearish={is_bearish}"
        )
        return regime

    except Exception as e:
        logger.warning(f"[KSA] Regime detection failed (non-fatal): {e}")
        return default_regime


# ---------------------------------------------------------------------------
# Price data fetch
# ---------------------------------------------------------------------------

def _normalise_ohlcv(raw: "pd.DataFrame", ticker: str) -> "pd.DataFrame | None":
    """
    Normalise an OHLCV DataFrame (any column casing) to lowercase snake-case.
    Returns None if required columns are missing or fewer than 30 rows remain.
    """
    raw = raw.copy()

    # Flatten MultiIndex columns (yfinance >= 0.2)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower()
                       for c in raw.columns]
    else:
        raw.columns = [str(c).lower() for c in raw.columns]

    # date column may arrive as "Date" (title-cased) after reset_index
    if "date" not in raw.columns and raw.index.name and raw.index.name.lower() == "date":
        raw = raw.reset_index()
        raw.columns = [str(c).lower() for c in raw.columns]

    # adj close / adjusted_close → close (if close absent)
    for alt in ("adj close", "adjusted_close", "adjclose"):
        if alt in raw.columns and "close" not in raw.columns:
            raw.rename(columns={alt: "close"}, inplace=True)
            break

    required = {"date", "open", "high", "low", "close", "volume"}
    missing  = required - set(raw.columns)
    if missing:
        logger.debug(f"[KSA] {ticker}: missing columns {missing}")
        return None

    df = raw[["date", "open", "high", "low", "close", "volume"]].copy()
    df.dropna(subset=["close"], inplace=True)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if len(df) < 30:
        logger.debug(f"[KSA] {ticker}: only {len(df)} rows after cleaning — insufficient")
        return None
    return df


def _fetch_ticker_data(ticker: str, days: int = 120) -> "pd.DataFrame | None":
    """
    Download ~6 months of daily OHLCV data for a Tadawul ticker.

    Provider chain:
      1. EODHD (primary) — reliable Tadawul coverage, requires EODHD_API_KEY
      2. yfinance (fallback) — free but incomplete for some .SR symbols

    Returns a clean DataFrame with lowercase columns:
        date, open, high, low, close, volume
    Returns None if both providers fail or data is insufficient (<30 rows).
    """
    from datetime import datetime, timedelta

    start = datetime.utcnow() - timedelta(days=180)
    end   = datetime.utcnow()

    # ---- 1. EODHD (primary) ---------------------------------------------
    try:
        from xmore_data.providers.eodhd_provider import EODHDProvider
        eodhd = EODHDProvider()
        if eodhd.enabled:
            raw = eodhd.fetch(ticker, interval="1d", start=start, end=end)
            if raw is not None and not raw.empty:
                df = _normalise_ohlcv(raw, ticker)
                if df is not None:
                    logger.debug(f"[KSA] {ticker}: EODHD — {len(df)} rows")
                    return df
    except Exception as e:
        logger.debug(f"[KSA] {ticker}: EODHD fetch failed (trying yfinance): {e}")

    # ---- 2. yfinance (fallback) -----------------------------------------
    try:
        raw = yf.download(
            ticker,
            period="6mo",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or len(raw) == 0:
            logger.debug(f"[KSA] {ticker}: yfinance returned empty DataFrame")
            return None

        raw = raw.reset_index()
        df = _normalise_ohlcv(raw, ticker)
        if df is not None:
            logger.debug(f"[KSA] {ticker}: yfinance — {len(df)} rows")
        return df

    except Exception as e:
        logger.warning(f"[KSA] {ticker}: data fetch error (non-fatal): {e}")
        return None


# ---------------------------------------------------------------------------
# Market data summary
# ---------------------------------------------------------------------------

def _build_market_data(df: pd.DataFrame, ticker: str) -> dict:
    """
    Derive summary statistics from a ticker's price DataFrame.

    Returns dict with:
        ticker, current_price, volatility_20d, avg_volume, current_volume,
        price_52w_high, price_52w_low
    """
    md: dict = {"ticker": ticker}

    # Current price
    try:
        md["current_price"] = float(df["close"].iloc[-1])
    except Exception:
        md["current_price"] = None

    # 20-day daily return volatility (std of simple returns)
    try:
        if len(df) >= 21:
            returns = df["close"].pct_change().dropna().tail(20)
            md["volatility_20d"] = float(returns.std())
        else:
            md["volatility_20d"] = None
    except Exception:
        md["volatility_20d"] = None

    # Average volume over last 20 sessions
    try:
        if "volume" in df.columns and len(df) >= 20:
            md["avg_volume"] = float(df["volume"].tail(20).mean())
        elif "volume" in df.columns:
            md["avg_volume"] = float(df["volume"].mean())
        else:
            md["avg_volume"] = None
    except Exception:
        md["avg_volume"] = None

    # Most-recent session volume
    try:
        md["current_volume"] = (
            float(df["volume"].iloc[-1]) if "volume" in df.columns else None
        )
    except Exception:
        md["current_volume"] = None

    # 52-week high / low (up to 252 trading sessions)
    try:
        window = df["close"].tail(252) if len(df) >= 252 else df["close"]
        md["price_52w_high"] = float(window.max())
        md["price_52w_low"]  = float(window.min())
    except Exception:
        md["price_52w_high"] = None
        md["price_52w_low"]  = None

    return md


# ---------------------------------------------------------------------------
# Run agents for a single ticker
# ---------------------------------------------------------------------------

def _run_agents_for_ticker(
    ticker: str,
    df: pd.DataFrame,
    market_data: dict,
    conn,
    config: dict,
) -> list:
    """
    Run all available signal agents for one Tadawul ticker.
    Every agent call is wrapped in try/except -- a single agent failure is
    non-fatal and the pipeline continues with whichever agents succeeded.

    Agents invoked (in order):
      1. MACrossoverAgent  (agents.agent_ma)
      2. RSIAgent          (agents.agent_rsi)
      3. VolumeAgent       (agents.agent_volume)
      4. MLAgent           (agents.agent_ml)
      5. GeminiAgent       (agents.gemini_agent) -- optional, KSA context injected

    Returns a list of signal dicts (one per agent that succeeded and returned a result).
    """
    signals: list = []

    # ---- 1. MA Crossover Agent ------------------------------------------
    try:
        from agents.agent_ma import MAAgent
        ma_agent = MAAgent()
        result = ma_agent.predict_signal(df, symbol=ticker, market_config=config)
        if result:
            result.setdefault("agent_name", "MA_Crossover_Agent")
            signals.append(result)
    except Exception as e:
        logger.debug(f"[KSA] {ticker} MA agent error (non-fatal): {e}")

    # ---- 2. RSI Agent ---------------------------------------------------
    try:
        from agents.agent_rsi import RSIAgent
        rsi_agent = RSIAgent()
        result = rsi_agent.predict_signal(df, symbol=ticker, market_config=config)
        if result:
            result.setdefault("agent_name", "RSI_Agent")
            signals.append(result)
    except Exception as e:
        logger.debug(f"[KSA] {ticker} RSI agent error (non-fatal): {e}")

    # ---- 3. Volume Agent ------------------------------------------------
    try:
        from agents.agent_volume import VolumeAgent
        vol_agent = VolumeAgent()
        result = vol_agent.predict_signal(df, symbol=ticker, market_config=config)
        if result:
            result.setdefault("agent_name", "Volume_Spike_Agent")
            signals.append(result)
    except Exception as e:
        logger.debug(f"[KSA] {ticker} Volume agent error (non-fatal): {e}")

    # ---- 4. ML Agent ----------------------------------------------------
    try:
        from agents.agent_ml import MLAgent
        ml_agent = MLAgent()
        result = ml_agent.predict_signal(df, symbol=ticker, market_config=config)
        if result:
            result.setdefault("agent_name", "ML_RandomForest")
            signals.append(result)
    except Exception as e:
        logger.debug(f"[KSA] {ticker} ML agent error (non-fatal): {e}")

    # ---- 5. Gemini LLM Agent (optional) ---------------------------------
    try:
        from agents.gemini_agent import GeminiAgent
        gemini_agent = GeminiAgent()
        if gemini_agent._enabled:
            # Inject KSA-specific market context so Gemini understands the exchange
            ksa_context = (
                f"Ticker: {ticker} | Exchange: Saudi Exchange (Tadawul) | "
                f"Market: KSA | Currency: SAR | "
                f"Trading hours: 10:00-15:00 AST Sun-Thu | "
                f"Current price: {market_data.get('current_price', 'N/A')} SAR | "
                f"Volatility (20d): {market_data.get('volatility_20d', 'N/A')}"
            )
            result = gemini_agent.predict_signal_with_context(
                df,
                symbol=ticker,
                extra_context=ksa_context,
                market_config=config,
            )
            if result:
                result.setdefault("agent_name", "Gemini_LLM_Agent")
                signals.append(result)
    except Exception as e:
        logger.debug(f"[KSA] {ticker} Gemini agent error (non-fatal): {e}")

    return signals


# ---------------------------------------------------------------------------
# Consensus engine
# ---------------------------------------------------------------------------

def _run_consensus(
    ticker: str,
    signals: list,
    market_data: dict,
    regime: dict,
    conn,
) -> dict:
    """
    Pass agent signals through the shared consensus engine with KSA regime context.
    Writes the consensus result to consensus_results table with market_id='KSA'.

    Returns the consensus result dict. Never raises -- returns a safe default on error.
    """
    result: dict = {
        "ticker":       ticker,
        "final_signal": "HOLD",
        "conviction":   "LOW",
        "xmore_score":  50,
        "market_id":    MARKET_ID,
    }
    try:
        from agents.consensus_engine import run_consensus

        # Map our simple regime dict to the format consensus_engine expects
        regime_for_consensus = {
            "regime_label_en":   regime.get("label", "Calm"),
            "current_regime":    0 if regime.get("label") == "Calm" else 1,
            "regime_confidence": 0.70,
            "is_bearish":        regime.get("is_bearish", False),
        }

        consensus = run_consensus(
            symbol=ticker,
            agent_signals=signals,
            market_data=market_data,
            market_regime=regime_for_consensus,
            db_conn=conn,
        )
        if consensus:
            result.update(consensus)
            result["market_id"] = MARKET_ID

    except Exception as e:
        logger.warning(f"[KSA] {ticker}: consensus engine error (non-fatal): {e}")
        return result

    # Persist to consensus_results (best-effort)
    try:
        cols = _get_table_columns(conn, "consensus_results")
        payload = {"symbol": ticker}
        if "prediction_date" in cols:
            payload["prediction_date"] = datetime.date.today()
        if "date" in cols:
            payload["date"] = datetime.date.today()
        if "final_signal" in cols:
            payload["final_signal"] = result.get("final_signal", "HOLD")
        if "conviction" in cols:
            payload["conviction"] = result.get("conviction", "LOW")
        if "xmore_score" in cols:
            payload["xmore_score"] = result.get("xmore_score", 50)
        if "market_id" in cols:
            payload["market_id"] = MARKET_ID
        if "signal_count" in cols:
            payload["signal_count"] = len(signals)
        if "created_at" in cols:
            payload["created_at"] = datetime.datetime.utcnow()

        col_names = list(payload.keys())
        placeholders = ", ".join(["%s"] * len(col_names))
        columns_sql = ", ".join(col_names)
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO consensus_results ({columns_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
            [payload[c] for c in col_names],
        )
        conn.commit()
    except Exception as _db_err:
        logger.debug(
            f"[KSA] consensus_results write skipped for {ticker}: {_db_err}"
        )
        try:
            conn.rollback()
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# DB signal storage
# ---------------------------------------------------------------------------

def _store_signal(conn, ticker: str, consensus_result: dict, market_data: dict = None) -> None:
    """
    INSERT a consensus signal into trade_recommendations with market_id='KSA'.
    Uses ON CONFLICT DO NOTHING to be idempotent on re-runs within the same day.

    Columns written:
        symbol, recommendation_date, signal_type, action, close_price,
        conviction, xmore_score, market_id, notes, created_at
    """
    try:
        final_signal = consensus_result.get("final_signal", "HOLD")
        conviction   = consensus_result.get("conviction", "LOW")
        xmore_score  = consensus_result.get("xmore_score", 50)
        confidence_map = {"LOW": 55, "MEDIUM": 70, "HIGH": 85, "VERY_HIGH": 92}
        numeric_confidence = confidence_map.get(str(conviction).upper(), 60)

        # Map directional signal to action for evaluate_performance compat
        _ACTION_MAP = {"UP": "BUY", "DOWN": "SELL", "BUY": "BUY", "SELL": "SELL"}
        action = _ACTION_MAP.get(final_signal, "HOLD")

        # close_price is required by the evaluation engine
        close_price = None
        if market_data:
            close_price = market_data.get("current_price") or market_data.get("close")

        notes = consensus_result.get("notes") or json.dumps(
            {
                "market_id": MARKET_ID,
                "source":    "run_agents_ksa",
                "agents":    consensus_result.get("agent_signals", []),
            }
        )

        cols = _get_table_columns(conn, "trade_recommendations")
        payload = {"symbol": ticker, "recommendation_date": datetime.date.today()}
        if "action" in cols:
            payload["action"] = action
        if "signal" in cols:
            payload["signal"] = final_signal
        if "signal_type" in cols:
            payload["signal_type"] = final_signal
        if "final_signal" in cols:
            payload["final_signal"] = final_signal
        if "confidence" in cols:
            payload["confidence"] = numeric_confidence
        if "conviction" in cols:
            payload["conviction"] = conviction
        if "close_price" in cols:
            payload["close_price"] = close_price
        if "xmore_score" in cols:
            payload["xmore_score"] = xmore_score
        if "market_id" in cols:
            payload["market_id"] = MARKET_ID
        if "notes" in cols:
            payload["notes"] = notes
        if "reasons" in cols:
            payload["reasons"] = notes
        if "created_at" in cols:
            payload["created_at"] = datetime.datetime.utcnow()
        if "updated_at" in cols:
            payload["updated_at"] = datetime.datetime.utcnow()

        col_names = list(payload.keys())
        placeholders = ", ".join(["%s"] * len(col_names))
        columns_sql = ", ".join(col_names)

        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO trade_recommendations ({columns_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
            [payload[c] for c in col_names],
        )
        conn.commit()
        logger.debug(
            f"[KSA] Signal stored for {ticker}: {final_signal} ({conviction}) "
            f"close={close_price}"
        )

    except Exception as e:
        logger.warning(f"[KSA] Failed to store signal for {ticker}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def execute(args) -> None:
    """
    Full KSA/Tadawul daily signal pipeline.

    Steps:
      1. Holiday / weekend guard
      2. Open PostgreSQL connection via DATABASE_URL
      3. Run KSA intelligence layer  (returns material tickers list)
      4. Run KSA Telegram reader
      5. Detect TASI market regime
      6. Select ticker universe (single or full)
      7. Per-ticker: fetch data -> run agents -> apply material boost -> consensus -> store
      8. Publish approved signals to WhatsApp
    """
    # ---- 1. Holiday check ------------------------------------------------
    if is_holiday() and not args.force_run:
        logger.info("[KSA] Saudi holiday or weekend -- skipping pipeline")
        return

    today = datetime.date.today()
    logger.info(f"[KSA] Pipeline starting for {today}")

    # ---- 2. DB connection ------------------------------------------------
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        if args.dry_run:
            # Allow local dry-run via shared SQLite fallback
            logger.warning("[KSA] DATABASE_URL not set — using SQLite fallback for dry-run")
            import sqlite3
            _sqlite_path = os.path.join(os.path.dirname(__file__), "stocks.db")
            conn = sqlite3.connect(_sqlite_path)
            conn.row_factory = sqlite3.Row
        else:
            logger.error("[KSA] DATABASE_URL not set -- aborting")
            return
    else:
        try:
            conn = psycopg2.connect(db_url)
        except Exception as e:
            logger.error(f"[KSA] Cannot connect to database: {e}")
            return

    # ---- 3. Intelligence layer -------------------------------------------
    material_tickers: list = []
    try:
        from agents.intelligence.ksa_intelligence.ksa_run_intelligence import (
            run_ksa_intelligence,
        )
        material_tickers = run_ksa_intelligence(conn) or []
        logger.info(
            f"[KSA] Intelligence layer complete: {len(material_tickers)} material tickers"
        )
    except Exception as e:
        logger.warning(f"[KSA] Intelligence error (non-fatal): {e}")

    # ---- 4. Telegram reader ----------------------------------------------
    try:
        from engines.telegram_reader_ksa import run_telegram_pipeline_ksa
        run_telegram_pipeline_ksa(conn, hours_back=25)
        logger.info("[KSA] Telegram pipeline complete")
    except Exception as e:
        logger.warning(f"[KSA] Telegram error (non-fatal): {e}")

    # ---- 5. Regime detection ---------------------------------------------
    regime = _detect_market_regime(conn)
    logger.info(
        f"[KSA] Market regime: {regime.get('label')} | "
        f"bearish={regime.get('is_bearish')} | "
        f"TASI={regime.get('tasi_price')} | MA20={regime.get('ma20')}"
    )

    # ---- 6. Select tickers -----------------------------------------------
    if args.ticker:
        tickers = [args.ticker]
        logger.info(f"[KSA] Single-ticker mode: {args.ticker}")
    else:
        tickers = list(KSA_INITIAL_UNIVERSE) if KSA_INITIAL_UNIVERSE else list(KSA_TOP50)
        logger.info(f"[KSA] Universe: {len(tickers)} tickers")

    if not tickers:
        logger.error("[KSA] Empty ticker universe -- aborting")
        conn.close()
        return

    # ---- 7. Per-ticker agent loop ----------------------------------------
    all_results: list = []
    processed = 0
    skipped   = 0

    for ticker in tickers:
        try:
            # Fetch price data
            df = _fetch_ticker_data(ticker)
            if df is None or len(df) < 30:
                logger.warning(f"[KSA] {ticker}: insufficient data -- skipping")
                skipped += 1
                continue

            # Build market data summary
            market_data = _build_market_data(df, ticker)

            # Run all 5 agents
            signals = _run_agents_for_ticker(ticker, df, market_data, conn, TADAWUL_CONFIG)
            if not signals:
                logger.warning(
                    f"[KSA] {ticker}: no agent signals returned -- skipping"
                )
                skipped += 1
                continue

            # Apply material-ticker confidence boost (+15%, capped at 100)
            if ticker in material_tickers:
                for s in signals:
                    old_conf = s.get("confidence", 50)
                    s["confidence"] = min(100, old_conf * 1.15)
                logger.debug(
                    f"[KSA] {ticker}: material-ticker confidence boost applied"
                )

            # Run consensus engine
            consensus = _run_consensus(ticker, signals, market_data, regime, conn)

            # ── Signal enrichment (drivers, risk_level, ATR%) ─────────────
            try:
                from engines.signal_enrichment import enrich_signal
                consensus = enrich_signal(consensus, df, consensus.get("final_signal", "HOLD"), market_data)
            except Exception as _e:
                logger.debug(f"[KSA] {ticker}: enrichment skipped: {_e}")

            # ── Tier 2 transaction cost gate (Tadawul ~38 bps RT) ─────────
            # Kill directional signals whose expected 5-day move can't clear
            # costs. expected_move_pct is 1-day ATR%, so scale by sqrt(5) to
            # get horizon-appropriate estimate.
            _TADAWUL_RT_COST_PCT = 0.40   # 38.2 bps round-trip, rounded up
            _MIN_NET_MOVE_PCT    = 1.00   # 1.0 % minimum net profit
            _HOLDING_DAYS        = 5
            import math as _math
            _HORIZON_SCALE       = _math.sqrt(_HOLDING_DAYS)  # ~2.236
            _MIN_THRESHOLD_PCT   = _TADAWUL_RT_COST_PCT + _MIN_NET_MOVE_PCT
            if consensus.get("final_signal") in ("UP", "DOWN"):
                em_pct = consensus.get("expected_move_pct")
                if em_pct is not None:
                    horizon_move_pct = em_pct * _HORIZON_SCALE
                    if horizon_move_pct < _MIN_THRESHOLD_PCT:
                        logger.info(
                            f"[KSA] {ticker}: cost gate: 5d move {horizon_move_pct:.2f}% < "
                            f"{_MIN_THRESHOLD_PCT:.2f}% → HOLD"
                        )
                        consensus["final_signal"] = "HOLD"
                        consensus["conviction"]   = "LOW"

            # Store to DB (skip in dry-run mode)
            if not args.dry_run:
                _store_signal(conn, ticker, consensus, market_data=market_data)

            all_results.append(consensus)
            processed += 1

            final = consensus.get("final_signal", "HOLD")
            conv  = consensus.get("conviction", "LOW")
            score = consensus.get("xmore_score", 50)
            logger.info(
                f"[KSA] {ticker}: {final} | conviction={conv} | score={score}"
            )

        except Exception as e:
            logger.warning(f"[KSA] {ticker}: unhandled error (non-fatal): {e}")
            logger.debug(traceback.format_exc())
            skipped += 1

    logger.info(
        f"[KSA] Agent loop complete -- processed={processed} "
        f"skipped={skipped} total_results={len(all_results)}"
    )

    # ---- 8. WhatsApp publish ---------------------------------------------
    if not args.dry_run and all_results:
        try:
            from engines.whatsapp_publisher_ksa import publish_ksa_daily

            approved = [
                r for r in all_results
                if r.get("final_signal") in ("UP", "DOWN", "BUY", "SELL")
            ]
            if approved:
                publish_ksa_daily(signals=approved)
                logger.info(
                    f"[KSA] WhatsApp: published {len(approved)} approved signals"
                )
            else:
                logger.info("[KSA] WhatsApp: no approved signals to publish today")
        except Exception as e:
            logger.warning(f"[KSA] WhatsApp error (non-fatal): {e}")
    elif args.dry_run:
        logger.info(
            "[KSA] Dry-run mode -- DB writes and WhatsApp publish skipped"
        )

    # ---- 9. Clean up --------------------------------------------------------
    try:
        conn.close()
    except Exception:
        pass

    logger.info(
        f"[KSA] Pipeline complete -- {len(all_results)} signals processed on {today}"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [KSA] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Xmore KSA Signal Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Fetch data and run agents but do not write to DB or publish",
    )
    parser.add_argument(
        "--ticker",
        default=None,
        metavar="TICKER",
        help="Run pipeline for a single ticker only, e.g. 2222.SR",
    )
    parser.add_argument(
        "--force-run",
        action="store_true",
        default=False,
        help="Bypass Saudi holiday/weekend check and run the pipeline anyway",
    )

    args = parser.parse_args()
    execute(args)
