"""DCF Valuation Agent — provides a weekly valuation signal for consensus."""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from agents.agent_base import BaseAgent, AgentSignal
from agents.dcf.dcf_store import get_latest_composite_dcf
from database import get_connection

logger = logging.getLogger(__name__)


_CONFIDENCE_MAP = {
    "HIGH": 90.0,
    "MEDIUM": 70.0,
    "LOW": 40.0,
}


class DCFValuationAgent(BaseAgent):
    """Agent that returns a valuation signal based on the latest DCF composite."""

    def __init__(self):
        super().__init__("DCF_Valuation_Agent")

    def predict_signal(self, data, symbol: str = "", sentiment: Optional[Dict[str, Any]] = None) -> dict:
        """Return a signal derived from the latest DCF composite valuation."""
        try:
            with get_connection() as conn:
                dcf = get_latest_composite_dcf(conn, symbol)
        except Exception as e:
            logger.debug(f"[DCF Agent] Failed to load DCF for {symbol}: {e}")
            dcf = None

        if not dcf or not dcf.get("valuation_label"):
            return AgentSignal(
                agent_name=self.name,
                symbol=symbol,
                prediction="HOLD",
                confidence=30.0,
                reasoning={"reason": "no_dcf_available"}
            ).to_dict()

        label = dcf["valuation_label"]
        conf = dcf.get("dcf_confidence", "LOW")
        mos = dcf.get("margin_of_safety")
        iv = dcf.get("intrinsic_per_share")
        price = dcf.get("current_price")

        if label in ("DEEP_VALUE", "UNDERVALUED"):
            prediction = "UP"
        elif label in ("OVERVALUED", "SPECULATIVE"):
            prediction = "DOWN"
        else:
            prediction = "HOLD"

        confidence = _CONFIDENCE_MAP.get(conf, 40.0)

        reasoning = {
            "valuation_label": label,
            "dcf_confidence": conf,
            "margin_of_safety": mos,
            "intrinsic_value": iv,
            "current_price": price,
            "computed_at": dcf.get("computed_at"),
        }

        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            prediction=prediction,
            confidence=confidence,
            reasoning=reasoning,
        ).to_dict()
