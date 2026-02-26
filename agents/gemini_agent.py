"""
Gemini LLM Agent — 5th trading agent for Xmore.

Unlike the 4 technical agents (RSI, MA, Volume, ML), this agent:
- Runs AFTER the other agents so it can see their signals
- Uses Google Gemini 2.5 Flash to synthesise price data + agent signals + sentiment
- Returns a buy/sell/hold recommendation with natural-language reasoning
- Gracefully falls back to HOLD (0 confidence) when Gemini is unavailable

Output matches the AgentSignal dict format used by run_agents.py and the
consensus engine, so no changes are needed to those interfaces.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Agent identity — must match the key in config.AGENT_WEIGHTS
AGENT_NAME = "Gemini_LLM_Agent"

# Prediction mapping from Gemini signal text → standard UP/DOWN/HOLD
_SIGNAL_MAP = {
    "buy":  "UP",
    "sell": "DOWN",
    "hold": "HOLD",
}


class GeminiAgent:
    """
    LLM-powered trading agent using Google Gemini 2.5 Flash.

    Usage in run_agents.py:
        gemini_agent = GeminiAgent()
        signal = gemini_agent.predict_signal_with_context(df, symbol, sentiment, other_signals)
        agent_signals.append(signal)
    """

    def __init__(self):
        self.name = AGENT_NAME
        api_key = os.getenv("GOOGLE_API_KEY", "")

        if api_key:
            try:
                from google import genai
                from google.genai import types as genai_types
                self._client = genai.Client(api_key=api_key)
                self._types = genai_types
                self._enabled = True
                logger.info("GeminiAgent: client initialised")
            except ImportError:
                logger.warning("GeminiAgent: google-genai not installed (pip install google-genai)")
                self._client = None
                self._enabled = False
        else:
            logger.warning("GeminiAgent: GOOGLE_API_KEY not set — agent will return HOLD")
            self._client = None
            self._enabled = False

    # ──────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────

    def predict_signal_with_context(
        self, df, symbol: str, sentiment: dict | None, other_signals: list
    ) -> dict:
        """
        Generate a structured AgentSignal dict using Gemini.

        Args:
            df:            Price DataFrame (date, open, high, low, close, volume)
            symbol:        EGX ticker (e.g. 'COMI.CA')
            sentiment:     Latest sentiment dict or None
            other_signals: List of AgentSignal dicts from the 4 technical agents

        Returns:
            dict matching AgentSignal.to_dict() format:
              {agent_name, symbol, prediction, confidence, reasoning, timestamp}
        """
        if not self._enabled or df is None or len(df) < 5:
            return self._fallback(symbol, reason="Gemini not configured or insufficient data")

        try:
            prompt = self._build_prompt(symbol, df, sentiment, other_signals)
            response_text = self._call_gemini(prompt)
            result = self._parse_response(response_text)

            prediction = _SIGNAL_MAP.get(result.get("signal", "hold").lower(), "HOLD")
            confidence = float(result.get("confidence", 0.0)) * 100  # convert 0-1 → 0-100
            reasoning_text = str(result.get("reasoning", ""))

            logger.info(f"GeminiAgent {symbol}: {prediction} ({confidence:.0f}%) — {reasoning_text[:80]}")

            return {
                "agent_name": self.name,
                "symbol": symbol,
                "prediction": prediction,
                "confidence": round(confidence, 1),
                "reasoning": {
                    "llm_signal": result.get("signal", "hold"),
                    "llm_confidence": result.get("confidence", 0.0),
                    "llm_reasoning": reasoning_text,
                    "other_agents_seen": len(other_signals),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"GeminiAgent error for {symbol}: {e}")
            return self._fallback(symbol, reason=f"API error: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _build_prompt(self, symbol: str, df, sentiment: dict | None, other_signals: list) -> str:
        # Last 20 closing prices + volumes
        price_rows = []
        for _, row in df.tail(20).iterrows():
            price_rows.append({
                "date": str(row["date"]) if "date" in df.columns else "N/A",
                "close": round(float(row["close"]), 3),
                "volume": int(row["volume"]) if "volume" in df.columns else 0,
            })

        # Compute a simple price trend descriptor
        if len(df) >= 5:
            pct_5d = (float(df["close"].iloc[-1]) - float(df["close"].iloc[-5])) / float(df["close"].iloc[-5]) * 100
            trend_text = f"{pct_5d:+.1f}% over last 5 days"
        else:
            trend_text = "insufficient history"

        # Sentiment summary
        if sentiment:
            sentiment_text = (
                f"{sentiment.get('sentiment_label', 'Neutral')} "
                f"(score {sentiment.get('avg_sentiment', 0):.2f}, "
                f"{sentiment.get('article_count', 0)} articles)"
            )
        else:
            sentiment_text = "No sentiment data available"

        # Other agent signals — summarised to save tokens
        signals_summary = []
        for s in other_signals:
            signals_summary.append({
                "agent": s.get("agent_name", "unknown"),
                "prediction": s.get("prediction", "HOLD"),
                "confidence": round(float(s.get("confidence", 0)), 1),
            })

        return f"""You are an expert analyst for the Egyptian Exchange (EGX).
Market: EGX trades Sunday–Thursday, 09:00–14:00 Cairo time (UTC+2).

Stock: {symbol}
Recent price trend: {trend_text}

Last 20 days of closing prices and volumes:
{json.dumps(price_rows, indent=2)}

Current news sentiment: {sentiment_text}

Signals from other AI agents today:
{json.dumps(signals_summary, indent=2)}

Based on the price trend, volume, sentiment, and agent signals, give your trading recommendation.

Respond with ONLY valid JSON in this exact format — no extra text:
{{"signal": "buy", "confidence": 0.72, "reasoning": "Your 1-2 sentence explanation here"}}

Rules:
- "signal" must be exactly one of: "buy", "sell", "hold"
- "confidence" must be a float 0.0–1.0
- "reasoning" must be plain English, under 200 characters
- Account for EGX-specific context: lower liquidity than US markets, EGP currency
- Be conservative: when uncertain, prefer "hold"
"""

    def _call_gemini(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=self._types.GenerateContentConfig(temperature=0.1),
        )
        return response.text.strip()

    def _parse_response(self, text: str) -> dict:
        """Extract JSON from Gemini response, tolerating markdown code fences."""
        # Strip ```json ... ``` wrappers if present
        if "```" in text:
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        # Find the first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON object found in Gemini response: {text[:200]}")

        return json.loads(text[start:end])

    def _fallback(self, symbol: str, reason: str = "") -> dict:
        """Return a neutral HOLD signal when Gemini is unavailable."""
        return {
            "agent_name": self.name,
            "symbol": symbol,
            "prediction": "HOLD",
            "confidence": 0.0,
            "reasoning": {
                "llm_signal": "hold",
                "llm_confidence": 0.0,
                "llm_reasoning": reason or "Gemini unavailable",
                "other_agents_seen": 0,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
