import pandas as pd
from typing import Optional, Dict, Any
from agents.agent_base import BaseAgent, AgentSignal
import config


class VolumeAgent(BaseAgent):
    """
    Volume Spike Agent.
    
    This agent generates signals based on unusual volume activity.
    High volume often precedes a significant price movement.
    
    Strategy:
    - Condition: Today's Volume > 1.5x Average Volume (20 days).
    - Signal UP (Buy): If price closed higher than yesterday (Green candle).
    - Signal DOWN (Sell): If price closed lower than yesterday (Red candle).
    - HOLD: Normal volume or flat price.
    """
    def __init__(self, volume_multiplier=1.5, avg_period=20):
        """
        Args:
            volume_multiplier (float): Factor to determine "high" volume (e.g., 1.5x).
            avg_period (int): Number of days for average volume calculation.
        """
        super().__init__("Volume_Spike_Agent")
        self.volume_multiplier = volume_multiplier
        self.avg_period = avg_period

    def predict(self, data: pd.DataFrame, sentiment: Optional[Dict[str, Any]] = None):
        """
        Analyze volume patterns to generate trading signals.

        Returns:
            str: "UP", "DOWN", or "HOLD".
        """
        if len(data) < self.avg_period + 1:
            return "HOLD"
        
        df = data.copy()
        df['vol_avg'] = df['volume'].rolling(window=self.avg_period).mean().shift(1)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        if current['volume'] > (current['vol_avg'] * self.volume_multiplier):
            if current['close'] > previous['close']:
                return "UP"
            elif current['close'] < previous['close']:
                return "DOWN"
                
        return "HOLD"

    def predict_signal(self, data: pd.DataFrame, symbol: str = "",
                       sentiment: Optional[Dict[str, Any]] = None,
                       market_config: Optional[Dict] = None) -> dict:
        """
        Generate structured prediction with volume reasoning data.
        
        Returns dict with volume metrics, spike detection, and price direction.
        """
        if len(data) < self.avg_period + 1:
            return AgentSignal(
                agent_name=self.name, symbol=symbol,
                prediction="HOLD", confidence=0.0,
                reasoning={"error": "insufficient_data", "rows": len(data)}
            ).to_dict()

        df = data.copy()
        df['vol_avg'] = df['volume'].rolling(window=self.avg_period).mean().shift(1)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        volume_today = int(current['volume']) if pd.notna(current['volume']) else 0
        vol_avg = float(current['vol_avg']) if pd.notna(current['vol_avg']) else 1
        volume_ratio = volume_today / vol_avg if vol_avg > 0 else 0
        is_spike = volume_ratio > 2.0
        
        # Determine price direction on current volume
        price_direction = "flat"
        if current['close'] > previous['close']:
            price_direction = "up"
        elif current['close'] < previous['close']:
            price_direction = "down"
        
        # Count consecutive high volume days
        consecutive_high = 0
        for i in range(1, min(len(df), 10)):
            row = df.iloc[-i]
            if pd.notna(row.get('vol_avg', None)) and row['volume'] > row['vol_avg'] * self.volume_multiplier:
                consecutive_high += 1
            else:
                break
        
        # Get prediction
        prediction = self.predict(data, sentiment)
        
        # Calculate confidence
        confidence = 40.0  # Base
        
        if is_spike:
            confidence += 15
            if volume_ratio > 3.0:
                confidence += 10  # Extreme spike
        
        if volume_ratio > self.volume_multiplier:
            confidence += 8
        
        if consecutive_high >= 2:
            confidence += 5
        
        # Volume confirms direction
        if prediction != "HOLD":
            confidence += 7
        
        # Low volume = low confidence
        if volume_ratio < 0.7:
            confidence = max(20, confidence - 15)
        
        confidence = min(90, max(15, confidence))
        
        reasoning = {
            "volume_today": volume_today,
            "volume_20d_avg": round(vol_avg),
            "volume_ratio": round(volume_ratio, 2),
            "is_spike": is_spike,
            "price_direction_on_spike": price_direction,
            "consecutive_high_volume_days": consecutive_high
        }
        
        return AgentSignal(
            agent_name=self.name, symbol=symbol,
            prediction=prediction, confidence=round(confidence, 1),
            reasoning=reasoning
        ).to_dict()
