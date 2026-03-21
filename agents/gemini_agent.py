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
import sqlite3
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
        self, df, symbol: str, sentiment: dict | None, other_signals: list,
        market_config: dict | None = None,
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

        news_context = self._fetch_recent_news(symbol)

        # Build a compact summary for embedding + pattern matching
        context_summary = {
            "trend": trend_text,
            "sentiment": sentiment_text,
            "signals": [f"{s.get('agent','?')}:{s.get('prediction','?')}@{s.get('confidence',0):.0f}" for s in signals_summary],
        }
        context_summary_text = json.dumps(context_summary)
        current_embedding = self._embed_text(context_summary_text) if self._client else None

        # Save context for future pattern matching (fire-and-forget, no crash if fails)
        self._save_prediction_context(symbol, context_summary, current_embedding)

        # Retrieve similar past outcomes (>0.7 similarity, only if has actual outcomes)
        pattern_context = self._get_similar_contexts(symbol, current_embedding)

        parts = []
        if news_context:
            parts.append(news_context)
        if pattern_context:
            parts.append(pattern_context)
        extra_context = ("\n\n" + "\n\n".join(parts)) if parts else ""

        context_labels = ["price trend", "volume", "sentiment", "agent signals"]
        if news_context:
            context_labels.append("recent news")
        if pattern_context:
            context_labels.append("historical patterns")
        based_on = ", ".join(context_labels)

        return f"""You are an expert analyst for the Egyptian Exchange (EGX).
Market: EGX trades Sunday–Thursday, 09:00–14:00 Cairo time (UTC+2).

Stock: {symbol}
Recent price trend: {trend_text}

Last 20 days of closing prices and volumes:
{json.dumps(price_rows, indent=2)}

Current news sentiment: {sentiment_text}

Signals from other AI agents today:
{json.dumps(signals_summary, indent=2)}{extra_context}

Based on the {based_on}, give your trading recommendation.

Respond with ONLY valid JSON in this exact format — no extra text:
{{"signal": "buy", "confidence": 0.72, "reasoning": "Your 1-2 sentence explanation here"}}

Rules:
- "signal" must be exactly one of: "buy", "sell", "hold"
- "confidence" must be a float 0.0–1.0
- "reasoning" must be plain English, under 200 characters
- Account for EGX-specific context: lower liquidity than US markets, EGP currency
- Make a decisive signal based on the weight of evidence; use "hold" only when signals genuinely contradict each other
- Bearish signals (falling price trend, negative sentiment, RSI rolling over, declining volume) should produce "sell", not "hold"
"""

    # ──────────────────────────────────────────────────────────────────────
    # Feature 5: Historical Pattern Matching
    # ──────────────────────────────────────────────────────────────────────

    def _embed_text(self, text: str):
        """Embed text via Gemini text-embedding-005. Returns float list or None."""
        try:
            result = self._client.models.embed_content(model='text-embedding-004', contents=text)
            return result.embeddings[0].values
        except Exception as e:
            logger.debug(f"Embed failed: {e}")
            return None

    def _cosine_similarity(self, a: list, b: list) -> float:
        import math
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    def _save_prediction_context(self, symbol: str, context_summary: dict, embedding):
        """Save current context snapshot + embedding to prediction_contexts."""
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from database import get_connection, _adapt_sql, DATABASE_URL
            today = datetime.utcnow().date().isoformat()
            ctx_json = json.dumps(context_summary)
            emb_json = json.dumps(embedding) if embedding else None
            with get_connection() as conn:
                cursor = conn.cursor()
                if DATABASE_URL:
                    cursor.execute("""
                        INSERT INTO prediction_contexts (symbol, prediction_date, context_json, embedding)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (symbol, prediction_date)
                        DO UPDATE SET context_json = EXCLUDED.context_json, embedding = EXCLUDED.embedding
                    """, (symbol, today, ctx_json, emb_json))
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO prediction_contexts
                          (symbol, prediction_date, context_json, embedding)
                        VALUES (?, ?, ?, ?)
                    """, (symbol, today, ctx_json, emb_json))
        except Exception as e:
            logger.debug(f"Save prediction context failed for {symbol}: {e}")

    def _get_similar_contexts(self, symbol: str, current_embedding) -> str:
        """Retrieve top-3 similar past prediction contexts that have known outcomes."""
        if not current_embedding:
            return ""
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from database import get_connection, _adapt_sql
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    _adapt_sql("""
                        SELECT prediction_date, context_json, embedding, actual_outcome, actual_change_pct
                        FROM prediction_contexts
                        WHERE symbol = ? AND actual_outcome IS NOT NULL AND embedding IS NOT NULL
                        ORDER BY prediction_date DESC
                        LIMIT 30
                    """),
                    (symbol,)
                )
                rows = cursor.fetchall()

            if not rows:
                return ""

            scored = []
            for row in rows:
                r = dict(row) if hasattr(row, 'keys') else {
                    "prediction_date": row[0], "context_json": row[1],
                    "embedding": row[2], "actual_outcome": row[3], "actual_change_pct": row[4]
                }
                try:
                    emb = json.loads(r["embedding"])
                    sim = self._cosine_similarity(current_embedding, emb)
                    scored.append({**r, "similarity": sim})
                except Exception as e:
                    logger.debug("Skipping malformed historical embedding for %s: %s", symbol, e)

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            top3 = [s for s in scored[:3] if s["similarity"] > 0.7]
            if not top3:
                return ""

            lines = ["Similar historical market situations (by price/signal pattern):"]
            for s in top3:
                chg = f"{s['actual_change_pct']:+.1f}%" if s.get('actual_change_pct') is not None else "N/A"
                lines.append(f"  - {s['prediction_date']}: actual {s['actual_outcome']} ({chg})")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Get similar contexts failed for {symbol}: {e}")
            return ""

    def _fetch_recent_news(self, symbol: str) -> str:
        """Fetch recent news headlines for a symbol from xmore_news.db and the main news table."""
        headlines = []

        # Source 1: xmore_news.db (standalone reliable news layer)
        xmore_db = os.path.join(os.path.dirname(__file__), '..', 'xmore_news_reliable', 'xmore_news.db')
        try:
            if os.path.exists(xmore_db):
                conn = sqlite3.connect(xmore_db)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT title, source, published_at FROM articles "
                    "WHERE detected_symbols LIKE ? ORDER BY published_at DESC LIMIT 5",
                    (f'%"{symbol}"%',)
                ).fetchall()
                conn.close()
                for r in rows:
                    headlines.append({"headline": r["title"], "source": r["source"], "date": str(r["published_at"] or "")})
        except Exception as e:
            logger.debug(f"xmore_news.db query skipped for {symbol}: {e}")

        # Source 2: main DB news table
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from database import get_connection, _adapt_sql, DATABASE_URL
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    _adapt_sql(
                        "SELECT headline, source, date, urgency_score FROM news WHERE symbol = ? "
                        "ORDER BY CASE source "
                        "WHEN 'egx_official' THEN 1 WHEN 'marketaux' THEN 2 "
                        "WHEN 'mubasher' THEN 3 WHEN 'argaam' THEN 4 ELSE 5 END, "
                        "urgency_score DESC NULLS LAST, date DESC LIMIT 10"
                    ),
                    (symbol,)
                )
                for row in cursor.fetchall():
                    d = dict(row) if hasattr(row, 'keys') else {"headline": row[0], "source": row[1], "date": str(row[2])}
                    headlines.append(d)
        except Exception as e:
            logger.debug(f"main DB news query skipped for {symbol}: {e}")

        # Deduplicate by headline prefix
        seen, unique = set(), []
        for item in headlines:
            key = item.get("headline", "").strip().lower()[:80]
            if key and key not in seen:
                seen.add(key)
                unique.append(item)

        if not unique:
            return ""

        lines = ["Recent news headlines:"]
        for item in unique[:10]:
            lines.append(f"  - [{item.get('date','?')}] {item.get('headline','')} ({item.get('source','')})")
        return "\n".join(lines)

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
