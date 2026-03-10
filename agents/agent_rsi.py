import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from agents.agent_base import BaseAgent, AgentSignal
import config


def _get_vol_regime(data: pd.DataFrame) -> str:
    """
    Classify recent volatility into Low / Normal / High regime.

    Uses EWMA std of daily returns (span=32, λ≈0.94 — same formula as
    features.py garch_ewm_vol so the signal is internally consistent).

    Thresholds (daily, not annualised):
      Low    < 1.5%  → use tighter period (faster signals)
      High   > 3.0%  → use wider period (filter noise)
      Normal otherwise
    """
    if len(data) < 20:
        return "normal"
    returns = data['close'].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0)
    ewma_vol = returns.ewm(span=32, min_periods=10).std().iloc[-1]
    if ewma_vol < 0.015:
        return "low"
    if ewma_vol > 0.030:
        return "high"
    return "normal"


_RSI_PERIODS = {"low": 10, "normal": 14, "high": 20}


class RSIAgent(BaseAgent):
    """
    Relative Strength Index (RSI) Agent.

    This agent uses the RSI indicator to identify overbought and oversold conditions.
    Sentiment data is used to confirm or adjust signals when available.

    Strategy:
    - UP (Buy): RSI < 30 (Oversold), boosted by bullish sentiment.
    - DOWN (Sell): RSI > 70 (Overbought), boosted by bearish sentiment.
    - HOLD: RSI between 30 and 70, or conflicting signals.
    """
    def __init__(self):
        """Initialize RSI Agent with default name."""
        super().__init__(name="RSI_Agent")

    def calculate_rsi(self, data, window=14):
        """
        Calculate RSI values using Wilder's smoothing method.

        Args:
            data (pd.DataFrame): DataFrame with 'close' price column.
            window (int): Lookback period. Defaults to 14.

        Returns:
            pd.Series: RSI values.
        """
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))
        avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def predict(self, data: pd.DataFrame, sentiment: Optional[Dict[str, Any]] = None):
        """
        Analyze price data and generate trading signal based on RSI thresholds.
        Sentiment is used as a confirmation signal when available.

        Returns:
            str: "UP", "DOWN", or "HOLD".
        """
        regime = _get_vol_regime(data)
        rsi_period = _RSI_PERIODS.get(regime, config.RSI_PERIOD)

        if len(data) < rsi_period + 1:
            return "HOLD"

        rsi_values = self.calculate_rsi(data, window=rsi_period)
        current_rsi = rsi_values.iloc[-1]

        if current_rsi < config.RSI_OVERSOLD:
            base_signal = "UP"
        elif current_rsi > config.RSI_OVERBOUGHT:
            base_signal = "DOWN"
        else:
            base_signal = "HOLD"
            # Detect bearish momentum even in neutral zone:
            # RSI falling sharply from elevated levels → early DOWN signal
            if len(data) >= 6:
                rsi_values_full = self.calculate_rsi(data, window=rsi_period)
                rsi_5d_ago = rsi_values_full.iloc[-6]
                rsi_diff = current_rsi - rsi_5d_ago
                # RSI crossed below 50 from above (trend reversal)
                if current_rsi < 50 and rsi_5d_ago > 52:
                    base_signal = "DOWN"
                # RSI falling sharply (>10 pts in 5d) from overbought territory
                elif rsi_diff < -10 and rsi_5d_ago > 58:
                    base_signal = "DOWN"

        if not sentiment or sentiment.get('article_count', 0) == 0:
            return base_signal

        sentiment_label = sentiment.get('sentiment_label', 'Neutral')
        avg_sentiment = sentiment.get('avg_sentiment', 0)

        if base_signal == "HOLD":
            if avg_sentiment > 0.3:
                return "UP"
            elif avg_sentiment < -0.3:
                return "DOWN"
            return "HOLD"

        if base_signal == "UP":
            if sentiment_label == "Bearish":
                return "HOLD"
            return "UP"

        if base_signal == "DOWN":
            if sentiment_label == "Bullish":
                return "HOLD"
            return "DOWN"

        return base_signal

    def predict_signal(self, data: pd.DataFrame, symbol: str = "",
                       sentiment: Optional[Dict[str, Any]] = None) -> dict:
        """
        Generate structured prediction with RSI reasoning data.
        
        Returns dict with RSI value, zone, trend, divergence analysis.
        """
        regime = _get_vol_regime(data)
        rsi_period = _RSI_PERIODS.get(regime, config.RSI_PERIOD)

        if len(data) < rsi_period + 1:
            return AgentSignal(
                agent_name=self.name, symbol=symbol,
                prediction="HOLD", confidence=0.0,
                reasoning={"error": "insufficient_data", "rows": len(data)}
            ).to_dict()

        df = data.copy()
        rsi_values = self.calculate_rsi(df, window=rsi_period)
        current_rsi = rsi_values.iloc[-1]

        # RSI from 5 days ago for trend
        rsi_5d_ago = rsi_values.iloc[-6] if len(rsi_values) >= 6 else rsi_values.iloc[0]
        
        # Determine RSI zone
        if current_rsi < 25:
            rsi_zone = "oversold"
        elif current_rsi < 35:
            rsi_zone = "approaching_oversold"
        elif current_rsi > 75:
            rsi_zone = "overbought"
        elif current_rsi > 65:
            rsi_zone = "approaching_overbought"
        else:
            rsi_zone = "neutral"
        
        # RSI trend
        rsi_diff = current_rsi - rsi_5d_ago
        if rsi_diff > 3:
            rsi_trend = "rising"
        elif rsi_diff < -3:
            rsi_trend = "falling"
        else:
            rsi_trend = "flat"
        
        # Check for RSI-Price divergence
        divergence = "none"
        if len(df) >= 10:
            price_now = df['close'].iloc[-1]
            price_prev = df['close'].iloc[-6] if len(df) >= 6 else df['close'].iloc[0]
            price_change = (price_now - price_prev) / price_prev if price_prev > 0 else 0
            
            if price_change < -0.02 and rsi_diff > 5:
                divergence = "bullish"   # Price falling but RSI rising
            elif price_change > 0.02 and rsi_diff < -5:
                divergence = "bearish"   # Price rising but RSI falling
        
        # Get base prediction
        prediction = self.predict(df, sentiment)
        
        # Calculate confidence
        confidence = 50.0

        # Extreme RSI = higher confidence
        if current_rsi < 20 or current_rsi > 80:
            confidence += 20
        elif current_rsi < 30 or current_rsi > 70:
            confidence += 12
        elif current_rsi < 40 or current_rsi > 60:
            confidence += 5

        # Momentum-based bearish signals are moderate confidence
        rsi_diff_val = current_rsi - rsi_5d_ago
        if prediction == "DOWN" and current_rsi < config.RSI_OVERBOUGHT:
            # Penalise slightly — these are momentum signals, not extreme readings
            confidence -= 10
            if rsi_diff_val < -10:
                confidence += 5  # Sharp fall is more convincing

        # Divergence boosts confidence
        if divergence == "bullish" and prediction == "UP":
            confidence += 10
        elif divergence == "bearish" and prediction == "DOWN":
            confidence += 10
        
        # Sentiment confirmation
        if sentiment and sentiment.get('article_count', 0) > 0:
            avg_sent = sentiment.get('avg_sentiment', 0)
            if (prediction == "UP" and avg_sent > 0.1) or (prediction == "DOWN" and avg_sent < -0.1):
                confidence += 5
        
        confidence = min(95, max(15, confidence))
        
        reasoning = {
            "rsi_value": round(current_rsi, 1),
            "rsi_period": rsi_period,
            "vol_regime": regime,
            "rsi_zone": rsi_zone,
            "rsi_trend": rsi_trend,
            "rsi_5d_ago": round(rsi_5d_ago, 1),
            "rsi_change_5d": round(rsi_diff, 1),
            "divergence": divergence
        }
        
        return AgentSignal(
            agent_name=self.name, symbol=symbol,
            prediction=prediction, confidence=round(confidence, 1),
            reasoning=reasoning
        ).to_dict()
