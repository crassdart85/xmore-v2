import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from agents.agent_base import BaseAgent, AgentSignal
import config


def _get_vol_regime(data: pd.DataFrame) -> str:
    """
    Classify recent volatility into Low / Normal / High regime.
    Uses EWMA std of daily returns (span=32, same as features.py garch_ewm_vol).

    Low  < 1.5% daily  → tighter windows (8/20) — signals quickly in calm markets
    High > 3.0% daily  → wider windows (15/40) — filter noise in volatile markets
    Normal otherwise   → default (10/30)
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


# (short_window, long_window) by regime
_MA_PERIODS = {
    "low":    (8,  20),
    "normal": (10, 30),
    "high":   (15, 40),
}


class MAAgent(BaseAgent):
    """
    Moving Average Crossover Agent.
    
    This agent generates signals based on the crossover of short-term and long-term
    moving averages (Golden Cross / Death Cross logic).
    
    Strategy:
    - UP (Buy): Short MA crosses above Long MA (Golden Cross) or Short > Long.
    - DOWN (Sell): Short MA crosses below Long MA (Death Cross) or Short < Long.
    - HOLD: Insufficient data.
    """
    def __init__(self, short_window=10, long_window=50):
        """
        Args:
            short_window (int): Period for short-term moving average.
            long_window (int): Period for long-term moving average.
        """
        super().__init__("MA_Crossover_Agent")
        self.short_window = short_window
        self.long_window = long_window

    def predict(self, data: pd.DataFrame, sentiment: Optional[Dict[str, Any]] = None):
        """
        Analyze price data and generate a trading signal.

        Args:
            data (pd.DataFrame): DataFrame containing 'close' price column.
            sentiment: Optional dict with sentiment data (not used by this agent).

        Returns:
            str: "UP", "DOWN", or "HOLD".
        """
        regime = _get_vol_regime(data)
        short_w, long_w = _MA_PERIODS.get(regime, (self.short_window, self.long_window))

        if len(data) < long_w + 1:
            return "HOLD"

        # Calculate moving averages
        data = data.copy()
        data['ma_short'] = data['close'].rolling(window=short_w).mean()
        data['ma_long'] = data['close'].rolling(window=long_w).mean()
        
        # Get current and previous values
        current = data.iloc[-1]
        previous = data.iloc[-2]
        
        # Check for crossover
        if current['ma_short'] > current['ma_long'] and previous['ma_short'] <= previous['ma_long']:
            return "UP"
        elif current['ma_short'] < current['ma_long'] and previous['ma_short'] >= previous['ma_long']:
            return "DOWN"
        elif current['ma_short'] > current['ma_long']:
            return "UP"
        else:
            return "DOWN"

    def predict_signal(self, data: pd.DataFrame, symbol: str = "",
                       sentiment: Optional[Dict[str, Any]] = None) -> dict:
        """
        Generate structured prediction with reasoning data.
        
        Returns dict with crossover details, MA values, and trend strength.
        """
        regime = _get_vol_regime(data)
        short_w, long_w = _MA_PERIODS.get(regime, (self.short_window, self.long_window))

        if len(data) < long_w + 1:
            return AgentSignal(
                agent_name=self.name, symbol=symbol,
                prediction="HOLD", confidence=0.0,
                reasoning={"error": "insufficient_data", "rows": len(data), "required": long_w + 1}
            ).to_dict()

        df = data.copy()
        df['ma_short'] = df['close'].rolling(window=short_w).mean()
        df['ma_long'] = df['close'].rolling(window=long_w).mean()
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Use unrounded values for logic
        sma_short = current['ma_short']
        sma_long = current['ma_long']
        price = current['close']
        
        # Determine crossover type and prediction
        crossover_type = "none"
        crossover_days_ago = None
        prediction = "HOLD"
        
        if current['ma_short'] > current['ma_long'] and previous['ma_short'] <= previous['ma_long']:
            crossover_type = "golden_cross"
            prediction = "UP"
            crossover_days_ago = 0
        elif current['ma_short'] < current['ma_long'] and previous['ma_short'] >= previous['ma_long']:
            crossover_type = "death_cross"
            prediction = "DOWN"
            crossover_days_ago = 0
        elif current['ma_short'] > current['ma_long']:
            crossover_type = "bullish_trend"
            prediction = "UP"
            # Find how many days ago the crossover happened
            for i in range(2, min(len(df), 30)):
                row = df.iloc[-i]
                if pd.notna(row['ma_short']) and pd.notna(row['ma_long']):
                    if row['ma_short'] <= row['ma_long']:
                        crossover_days_ago = i - 1
                        break
        else:
            crossover_type = "bearish_trend"
            prediction = "DOWN"
            for i in range(2, min(len(df), 30)):
                row = df.iloc[-i]
                if pd.notna(row['ma_short']) and pd.notna(row['ma_long']):
                    if row['ma_short'] >= row['ma_long']:
                        crossover_days_ago = i - 1
                        break
        
        # Calculate trend strength based on MA gap
        ma_gap_pct = abs(sma_short - sma_long) / sma_long * 100 if sma_long > 0 else 0
        if ma_gap_pct > 5:
            trend_strength = "strong"
        elif ma_gap_pct > 2:
            trend_strength = "moderate"
        else:
            trend_strength = "weak"

        price_above_short = bool(price > sma_short)

        # MA slope: compare current MAs to 5 days ago
        ma_slope_bearish = False
        sma_short_5d = df['ma_short'].iloc[-6] if len(df) >= 6 and pd.notna(df['ma_short'].iloc[-6]) else sma_short
        sma_long_5d  = df['ma_long'].iloc[-6]  if len(df) >= 6 and pd.notna(df['ma_long'].iloc[-6])  else sma_long
        short_slope = sma_short - sma_short_5d
        long_slope  = sma_long  - sma_long_5d
        # Both MAs declining = bearish underlying momentum even in bullish crossover
        if short_slope < 0 and long_slope < 0:
            ma_slope_bearish = True
        # If price has fallen below short MA while in a "bullish trend", override to DOWN
        if crossover_type == "bullish_trend" and not price_above_short and ma_slope_bearish:
            prediction = "DOWN"
            crossover_type = "bearish_slope_override"

        # Confidence: based on freshness of crossover and gap strength
        confidence = 50.0

        if crossover_days_ago is not None:
            if crossover_days_ago <= 3:
                confidence += 20  # Fresh crossover = high confidence
            elif crossover_days_ago <= 7:
                confidence += 10

        if trend_strength == "strong":
            confidence += 15
        elif trend_strength == "moderate":
            confidence += 8
        if (prediction == "UP" and price_above_short) or (prediction == "DOWN" and not price_above_short):
            confidence += 7  # Price confirms direction

        # Both MAs declining while in "bullish" zone lowers UP confidence
        if ma_slope_bearish and prediction == "UP":
            confidence -= 12

        confidence = min(95, max(20, confidence))

        reasoning = {
            f"sma_{short_w}": round(sma_short, 2),
            f"sma_{long_w}": round(sma_long, 2),
            "current_price": round(price, 2),
            "crossover_type": crossover_type,
            "crossover_days_ago": crossover_days_ago if crossover_days_ago is not None else ">30",
            f"price_above_sma{short_w}": price_above_short,
            "trend_strength": trend_strength,
            "ma_gap_pct": round(ma_gap_pct, 2),
            "ma_slope_bearish": ma_slope_bearish,
            "vol_regime": regime,
            "ma_periods": f"{short_w}/{long_w}"
        }
        
        return AgentSignal(
            agent_name=self.name, symbol=symbol,
            prediction=prediction, confidence=round(confidence, 1),
            reasoning=reasoning
        ).to_dict()