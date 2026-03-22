"""
Market Regime Filter — prevents new long positions during benchmark downtrends.

Uses a simple MA-distance rule rather than the HMM model in regime_model.py,
so it works without hmmlearn and runs in seconds during the signal pipeline.
"""

import logging
from datetime import datetime, timezone

import pandas as pd

from config.execution_config import (
    REGIME_TICKER, REGIME_MA_PERIOD, REGIME_BEARISH_BUFFER,
)
from database import get_connection
from xmore_data.data_manager import DataManager

logger = logging.getLogger("RegimeFilter")


class RegimeFilter:

    def __init__(self):
        self._cache = {"date": None, "regime": None, "benchmark": None, "ma20": None}
        self._data_manager = DataManager(use_cache=True, verbose=False)

    # ── Data fetch ───────────────────────────────────────────────────────────

    def fetch_egx30_data(self, lookback_days: int = 30):
        """Load benchmark close prices from DB first, then provider layer if needed."""
        cutoff = datetime.now(timezone.utc).date().isoformat()
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                placeholder = "%s" if hasattr(cursor, "mogrify") else "?"
                sql = f"""
                    SELECT date, close FROM prices
                    WHERE symbol IN ('TASI', '{REGIME_TICKER}', '^TASI')
                      AND date <= {placeholder}
                    ORDER BY date DESC
                    LIMIT {lookback_days * 3}
                """
                cursor.execute(sql, (cutoff,))
                rows = cursor.fetchall() or []
            if rows:
                records = []
                for row in rows:
                    if isinstance(row, dict):
                        records.append({"Date": row["date"], "Close": row["close"]})
                    else:
                        records.append({"Date": row[0], "Close": row[1]})
                df = pd.DataFrame(records)
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.sort_values("Date").reset_index(drop=True)
                if len(df) >= REGIME_MA_PERIOD:
                    return df
        except Exception as e:
            logger.warning(f"[RegimeFilter] DB benchmark load failed: {e}")

        try:
            end = datetime.now(timezone.utc)
            start = end - pd.Timedelta(days=lookback_days * 3)
            df = self._data_manager.fetch_data(
                REGIME_TICKER,
                interval="1d",
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                force_refresh=True,
            )
            return df[["Date", "Close"]]
        except Exception as e:
            logger.warning(f"[RegimeFilter] Provider fetch error: {e}")
            return pd.DataFrame()

    # ── Regime detection ─────────────────────────────────────────────────────

    def get_current_regime(self, force_refresh: bool = False) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()

        if not force_refresh and self._cache["date"] == today and self._cache["regime"]:
            return {
                "regime":              self._cache["regime"],
                "egx30_price":         self._cache["benchmark"],
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
            "benchmark": result["egx30_price"],
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
            f"(TASI {distance:.1f}% from MA20)",
        )
