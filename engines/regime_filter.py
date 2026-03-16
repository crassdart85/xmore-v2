"""
Market Regime Filter — prevents new long positions during EGX30 downtrends.

Uses a simple MA-distance rule rather than the HMM model in regime_model.py,
so it works without hmmlearn and runs in seconds during the signal pipeline.
"""

import logging
from datetime import datetime, timezone

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from config.execution_config import (
    REGIME_TICKER, REGIME_MA_PERIOD, REGIME_BEARISH_BUFFER,
)

logger = logging.getLogger("RegimeFilter")


class RegimeFilter:

    def __init__(self):
        self._cache = {"date": None, "regime": None, "egx30": None, "ma20": None}

    # ── Data fetch ───────────────────────────────────────────────────────────

    def fetch_egx30_data(self, lookback_days: int = 30):
        """Download EGX30 close prices via yfinance. Returns DataFrame or empty."""
        if not HAS_YFINANCE:
            logger.warning("[RegimeFilter] yfinance not installed — regime unavailable")
            try:
                import pandas as pd
                return pd.DataFrame()
            except ImportError:
                return None

        import pandas as pd
        try:
            raw = yf.download(
                REGIME_TICKER,
                period=f"{lookback_days}d",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            if raw is None or raw.empty:
                logger.warning(f"[RegimeFilter] No data returned for {REGIME_TICKER}")
                return pd.DataFrame()
            df = raw[["Close"]].reset_index()
            df.columns = ["Date", "Close"]
            return df
        except Exception as e:
            logger.warning(f"[RegimeFilter] Fetch error: {e}")
            return pd.DataFrame()

    # ── Regime detection ─────────────────────────────────────────────────────

    def get_current_regime(self, force_refresh: bool = False) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()

        if not force_refresh and self._cache["date"] == today and self._cache["regime"]:
            return {
                "regime":              self._cache["regime"],
                "egx30_price":         self._cache["egx30"],
                "ma20":                self._cache["ma20"],
                "distance_from_ma_pct": self._cache["distance"],
                "new_longs_allowed":   self._cache["regime"] == "BULL",
                "timestamp":           self._cache["date"],
            }

        df = self.fetch_egx30_data(lookback_days=30)

        # Fallback: if data unavailable, allow longs (fail-open)
        if df is None or df.empty or len(df) < REGIME_MA_PERIOD:
            logger.warning("[RegimeFilter] Insufficient data — defaulting to NEUTRAL")
            result = {
                "regime":              "NEUTRAL",
                "egx30_price":         None,
                "ma20":                None,
                "distance_from_ma_pct": 0.0,
                "new_longs_allowed":   False,
                "timestamp":           datetime.now(timezone.utc).isoformat(),
            }
            return result

        ma20          = float(df["Close"].rolling(REGIME_MA_PERIOD).mean().iloc[-1])
        current_price = float(df["Close"].iloc[-1])
        distance      = (current_price - ma20) / ma20 if ma20 > 0 else 0.0

        if distance >= REGIME_BEARISH_BUFFER:
            regime = "BULL"
        elif distance < 0:
            regime = "BEAR"
        else:
            regime = "NEUTRAL"

        result = {
            "regime":              regime,
            "egx30_price":         round(current_price, 2),
            "ma20":                round(ma20, 2),
            "distance_from_ma_pct": round(distance * 100, 2),
            "new_longs_allowed":   regime == "BULL",
            "timestamp":           datetime.now(timezone.utc).isoformat(),
        }

        self._cache.update({
            "date":     today,
            "regime":   regime,
            "egx30":    result["egx30_price"],
            "ma20":     result["ma20"],
            "distance": result["distance_from_ma_pct"],
        })
        return result

    # ── Public gate ──────────────────────────────────────────────────────────

    def is_long_allowed(self) -> tuple:
        info = self.get_current_regime()
        if info["new_longs_allowed"]:
            return True, "Market in BULL regime"
        distance = info.get("distance_from_ma_pct", 0.0)
        regime   = info["regime"]
        return (
            False,
            f"Market regime {regime} — new longs BLOCKED "
            f"(EGX30 {distance:.1f}% from MA20)",
        )
