"""
Technical Feature Engineering Module

Calculates 40+ technical indicators using TA-Lib (with pure-Python fallback).
Groups: Trend, Momentum, Volatility, Volume, Candlestick Patterns, EGX-specific.

Used by ML_RandomForest agent and other agents for signal generation.
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Try TA-Lib first, fall back to pure Python
try:
    import talib
    TALIB_AVAILABLE = True
    logger.info("TA-Lib loaded successfully")
except ImportError:
    TALIB_AVAILABLE = False
    logger.warning("TA-Lib not available, using pure Python fallback indicators")


def calculate_rsi(series, period=14):
    """Pure Python RSI calculation (fallback when TA-Lib unavailable)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def add_technical_indicators(df):
    """
    Add 40+ technical indicators to price DataFrame.
    Expects columns: ['open', 'high', 'low', 'close', 'volume']

    Uses TA-Lib when available (C-optimized), falls back to pure Python.

    Returns:
        pd.DataFrame: Input DataFrame with indicator columns added.
    """
    df = df.copy()

    if TALIB_AVAILABLE:
        df = _add_talib_indicators(df)
    else:
        df = _add_fallback_indicators(df)

    # EGX-specific features (from live feed data)
    df = _add_egx_features(df)

    # Clean NaN values — drop rows where lookback period hasn't been met
    max_lookback = 50  # SMA_50 requires 50 periods
    if len(df) > max_lookback:
        df = df.iloc[max_lookback:].copy()

    return df


def _add_talib_indicators(df):
    """Add indicators using TA-Lib (C-optimized, battle-tested)."""
    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)
    volume = df['volume'].values.astype(float)
    open_price = df['open'].values.astype(float)

    # ===================== TREND =====================
    # Moving Averages
    df['SMA_10'] = talib.SMA(close, timeperiod=10)
    df['SMA_30'] = talib.SMA(close, timeperiod=30)
    df['SMA_50'] = talib.SMA(close, timeperiod=50)
    df['EMA_12'] = talib.EMA(close, timeperiod=12)
    df['EMA_26'] = talib.EMA(close, timeperiod=26)

    # MACD
    df['MACD'], df['Signal_Line'], df['MACD_Hist'] = talib.MACD(close)

    # ADX — Average Directional Index (trend strength)
    df['ADX'] = talib.ADX(high, low, close, timeperiod=14)
    df['PLUS_DI'] = talib.PLUS_DI(high, low, close, timeperiod=14)
    df['MINUS_DI'] = talib.MINUS_DI(high, low, close, timeperiod=14)

    # ===================== MOMENTUM =====================
    # RSI
    df['RSI'] = talib.RSI(close, timeperiod=14)

    # CCI — Commodity Channel Index
    df['CCI'] = talib.CCI(high, low, close, timeperiod=20)

    # Williams %R
    df['WILLR'] = talib.WILLR(high, low, close, timeperiod=14)

    # Stochastic
    df['STOCH_K'], df['STOCH_D'] = talib.STOCH(high, low, close)

    # MFI — Money Flow Index (volume-weighted RSI)
    df['MFI'] = talib.MFI(high, low, close, volume, timeperiod=14)

    # ROC — Rate of Change
    df['ROC'] = talib.ROC(close, timeperiod=10)

    # ===================== VOLATILITY =====================
    # Bollinger Bands
    df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = talib.BBANDS(close, timeperiod=20)

    # ATR — Average True Range
    df['ATR'] = talib.ATR(high, low, close, timeperiod=14)

    # NATR — Normalized ATR (percentage)
    df['NATR'] = talib.NATR(high, low, close, timeperiod=14)

    # Returns and Volatility
    df['Returns'] = pd.Series(close).pct_change().values
    df['Volatility'] = pd.Series(df['Returns']).rolling(window=20).std().values

    # GARCH-inspired volatility features (no arch library required)
    df = _add_garch_inspired_features(df)

    # ===================== VOLUME =====================
    # OBV — On Balance Volume
    df['OBV'] = talib.OBV(close, volume)

    # AD — Accumulation/Distribution
    df['AD_Line'] = talib.AD(high, low, close, volume)

    # ===================== CANDLESTICK PATTERNS =====================
    df['DOJI'] = talib.CDLDOJI(open_price, high, low, close)
    df['HAMMER'] = talib.CDLHAMMER(open_price, high, low, close)
    df['ENGULFING'] = talib.CDLENGULFING(open_price, high, low, close)

    return df


def _add_fallback_indicators(df):
    """Pure Python fallback indicators (when TA-Lib is not installed)."""
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # ===================== TREND =====================
    df['SMA_10'] = close.rolling(window=10).mean()
    df['SMA_30'] = close.rolling(window=30).mean()
    df['SMA_50'] = close.rolling(window=50).mean()
    df['EMA_12'] = close.ewm(span=12, adjust=False).mean()
    df['EMA_26'] = close.ewm(span=26, adjust=False).mean()

    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']

    # ===================== MOMENTUM =====================
    df['RSI'] = calculate_rsi(close)

    # ROC
    df['ROC'] = close.pct_change(periods=10) * 100

    # Stochastic
    low_14 = low.rolling(window=14).min()
    high_14 = high.rolling(window=14).max()
    df['STOCH_K'] = ((close - low_14) / (high_14 - low_14)) * 100
    df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()

    # Williams %R
    df['WILLR'] = ((high_14 - close) / (high_14 - low_14)) * -100

    # CCI
    tp = (high + low + close) / 3
    tp_sma = tp.rolling(window=20).mean()
    tp_mad = tp.rolling(window=20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df['CCI'] = (tp - tp_sma) / (0.015 * tp_mad)

    # ===================== VOLATILITY =====================
    # Bollinger Bands
    df['BB_Middle'] = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (2 * bb_std)
    df['BB_Lower'] = df['BB_Middle'] - (2 * bb_std)

    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=14).mean()
    df['NATR'] = (df['ATR'] / close) * 100

    # Returns and Volatility
    df['Returns'] = close.pct_change()
    df['Volatility'] = df['Returns'].rolling(window=20).std()

    # GARCH-inspired volatility features
    df = _add_garch_inspired_features(df)

    # ===================== VOLUME =====================
    # OBV
    obv = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i-1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i-1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    df['OBV'] = obv

    # Placeholder columns for consistency with TA-Lib version
    df['ADX'] = np.nan
    df['PLUS_DI'] = np.nan
    df['MINUS_DI'] = np.nan
    df['MFI'] = np.nan
    df['AD_Line'] = np.nan
    df['DOJI'] = 0
    df['HAMMER'] = 0
    df['ENGULFING'] = 0

    return df


def _add_garch_inspired_features(df):
    """
    Add GARCH-inspired volatility dynamic features without requiring the arch library.

    Three features:
      garch_ewm_vol    — Exponentially-weighted std of returns (RiskMetrics EWMA,
                         λ≈0.94 ↔ span≈32). Approximates IGARCH(1,1) conditional vol.
                         Captures volatility clustering faster than a simple rolling std.
      vol_of_vol       — Rolling std of garch_ewm_vol (10-day). Measures how erratic
                         volatility itself is; high values → uncertainty about uncertainty.
      vol_persistence  — Lag-1 autocorrelation of squared returns over 20-day window.
                         Positive → vol is sticky/persistent; near-zero → mean-reverting.

    All three are normalised to avoid scale issues during RF training.
    """
    if 'Returns' not in df.columns:
        df['garch_ewm_vol']   = np.nan
        df['vol_of_vol']      = np.nan
        df['vol_persistence'] = np.nan
        return df

    returns = df['Returns'].fillna(0)

    # EWMA vol (span=32 ≈ λ=0.94 daily decay, RiskMetrics standard)
    df['garch_ewm_vol'] = returns.ewm(span=32, min_periods=10).std()

    # Vol-of-vol: how much is conditional vol changing day-to-day
    df['vol_of_vol'] = df['garch_ewm_vol'].rolling(window=10, min_periods=5).std()

    # Persistence: lag-1 ACF of squared returns (20-day rolling)
    sq_ret = returns ** 2
    df['vol_persistence'] = sq_ret.rolling(window=20, min_periods=10).apply(
        lambda x: float(pd.Series(x).autocorr(lag=1)) if len(x) >= 5 else 0.0,
        raw=False
    ).fillna(0)

    return df


def add_macro_features(df, macro_df):
    """
    Merge macro context (Brent crude, USD/EGP rate, EM equity) into the stock price DataFrame.

    Uses 5-day rolling returns for each macro series so the ML agent sees recent direction,
    not just the raw level (which varies in scale across instruments).

    macro_df must have columns: date, brent_close, usdegp_close, eem_close.
    Any missing macro series is filled with 0 (neutral / no signal).
    """
    macro_cols = ['brent_return_5d', 'usdegp_return_5d', 'eem_return_5d']

    if macro_df is None or len(macro_df) == 0:
        for col in macro_cols:
            df[col] = 0.0
        return df

    macro = macro_df.copy()
    if 'date' not in macro.columns:
        for col in macro_cols:
            df[col] = 0.0
        return df

    # Normalise date to string YYYY-MM-DD for merge. Some upstream sources can
    # leak a literal header row like 'date', which should be treated as invalid.
    macro_dates = pd.to_datetime(macro['date'], errors='coerce')
    macro = macro.loc[macro_dates.notna()].copy()
    if macro.empty:
        for col in macro_cols:
            df[col] = 0.0
        return df

    macro['date'] = macro_dates.loc[macro.index].dt.strftime('%Y-%m-%d')
    macro = macro.sort_values('date')

    for raw_col, ret_col in [
        ('brent_close',  'brent_return_5d'),
        ('usdegp_close', 'usdegp_return_5d'),
        ('eem_close',    'eem_return_5d'),
    ]:
        if raw_col in macro.columns:
            macro[ret_col] = macro[raw_col].pct_change(5)
        else:
            macro[ret_col] = 0.0

    # Normalise date on the price df too
    date_col = 'date' if 'date' in df.columns else None
    if date_col:
        df = df.copy()
        df_dates = pd.to_datetime(df[date_col], errors='coerce')
        df['_date_str'] = df_dates.dt.strftime('%Y-%m-%d')
        df = df.merge(
            macro[['date'] + macro_cols],
            left_on='_date_str', right_on='date',
            how='left', suffixes=('', '_macro')
        )
        df = df.drop(columns=['_date_str', 'date_macro'], errors='ignore')
    else:
        for col in macro_cols:
            df[col] = 0.0

    df[macro_cols] = df[macro_cols].fillna(0.0)
    return df


def _add_egx_features(df):
    """Add EGX-specific features from live feed data (if available)."""
    # Bid-Ask Spread (from EGX live feed)
    if 'bid' in df.columns and 'ask' in df.columns:
        df['bid_ask_spread'] = np.where(
            df['close'] > 0,
            (df['ask'] - df['bid']) / df['close'],
            0 
        )
    
    # 52-week range position
    if 'low_52w' in df.columns and 'high_52w' in df.columns:
        range_diff = df['high_52w'] - df['low_52w']
        df['range_52w_position'] = np.where(
            range_diff > 0,
            (df['close'] - df['low_52w']) / range_diff,
            0.5
        )

    return df


def add_sentiment_features(price_df, news_df):
    """
    Merge daily sentiment into price DataFrame.
    news_df should have ['date', 'sentiment_score']
    """
    if news_df is None or len(news_df) == 0:
        price_df['sentiment_score'] = 0
        return price_df

    # Coerce to numeric — PostgreSQL NULL comes back as None (object dtype), causing agg failure
    news_df = news_df.copy()
    news_df['sentiment_score'] = pd.to_numeric(news_df['sentiment_score'], errors='coerce')
    # Normalize date to string so merge works regardless of date/datetime/str type from PG or SQLite
    news_df['date'] = pd.to_datetime(news_df['date']).dt.strftime('%Y-%m-%d')
    price_df = price_df.copy()
    price_df['_date_str'] = pd.to_datetime(price_df['date']).dt.strftime('%Y-%m-%d')

    # Group news by date
    daily_sentiment = news_df.groupby('date')['sentiment_score'].mean().reset_index()

    # Merge on normalized date strings
    price_df = pd.merge(price_df, daily_sentiment, left_on='_date_str', right_on='date',
                        how='left', suffixes=('', '_sent'))
    price_df = price_df.drop(columns=['_date_str', 'date_sent'], errors='ignore')

    # Fill missing sentiment with 0 (neutral)
    price_df['sentiment_score'] = price_df['sentiment_score'].fillna(0)

    return price_df


def get_feature_columns():
    """
    Get the list of feature column names used by ML agents.

    Returns:
        list: Feature column names in consistent order.
    """
    return [
        # Price
        'open', 'high', 'low', 'close', 'volume',
        # Trend
        'SMA_10', 'SMA_30', 'SMA_50', 'EMA_12', 'EMA_26',
        'MACD', 'Signal_Line', 'MACD_Hist',
        'ADX', 'PLUS_DI', 'MINUS_DI',
        # Momentum
        'RSI', 'CCI', 'WILLR', 'STOCH_K', 'STOCH_D', 'MFI', 'ROC',
        # Volatility
        'BB_Upper', 'BB_Middle', 'BB_Lower', 'ATR', 'NATR', 'Volatility',
        # GARCH-inspired volatility dynamics
        'garch_ewm_vol', 'vol_of_vol', 'vol_persistence',
        # Volume
        'OBV', 'AD_Line',
        # Macro context
        'brent_return_5d', 'usdegp_return_5d', 'eem_return_5d',
        # Sentiment
        'sentiment_score',
    ]


def log_feature_importance(model, feature_names, symbol='', top_n=10):
    """
    Log top N feature importances from a trained model.

    Args:
        model: Trained model with feature_importances_ attribute
        feature_names: List of feature names
        symbol: Stock symbol for context
        top_n: Number of top features to log
    """
    if not hasattr(model, 'feature_importances_'):
        return

    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]

    prefix = f"[{symbol}] " if symbol else ""
    logger.info(f"{prefix}Top {top_n} feature importances:")
    for i, idx in enumerate(indices):
        if idx < len(feature_names):
            logger.info(f"  {i+1}. {feature_names[idx]}: {importances[idx]:.4f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"TA-Lib available: {TALIB_AVAILABLE}")
    print(f"Feature columns ({len(get_feature_columns())}): {get_feature_columns()}")
