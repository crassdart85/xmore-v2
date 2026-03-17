"""
news/classifier/event_classifier.py — Event type + drift direction classifier.

Two-stage classification:
  Stage 1 — Keyword rules (fast, auditable, zero latency, zero cost).
             Handles ~85% of financial news correctly.
  Stage 2 — Gemini LLM fallback for ambiguous cases.
             Only invoked when rule confidence is below threshold.

Every classification is deterministic for the rule-based stage, which is
critical for institutional auditability. The LLM stage output is logged with
the chunk so analysts can inspect why a particular classification was made.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Tuple

from news.models import DriftDirection, EventType, ProcessedChunk

logger = logging.getLogger(__name__)

# ── Keyword rule tables ───────────────────────────────────────────────────────
# Each entry: keywords (match any), positive_kw, negative_kw for direction.
# Lists intentionally bilingual (EN + AR) for EGX coverage.

CLASSIFICATION_RULES: dict[EventType, dict] = {
    EventType.RATE_DECISION: {
        "keywords": [
            "interest rate", "policy rate", "mpc", "monetary policy committee",
            "basis points", "bps", "rate hike", "rate cut", "rate hold",
            "overnight rate", "cbe rate", "sama rate", "lending rate",
            "deposit rate", "corridor",
            "seur al fa'ida", "سعر الفائدة", "لجنة السياسة النقدية",
            "معدل الفائدة", "البنك المركزي المصري",
        ],
        "pos_kw": ["cut", "reduce", "lower", "ease", "easing", "decline", "fell"],
        "neg_kw": ["hike", "raise", "increase", "tighten", "surge", "jumped"],
    },
    EventType.FX_MOVE: {
        "keywords": [
            "egp", "egyptian pound", "devaluation", "devalue", "fx", "usd/egp",
            "foreign exchange", "dollar rate", "exchange rate", "black market",
            "currency", "peg", "float", "revaluation",
            "الجنيه المصري", "سعر الصرف", "الدولار", "العملة",
        ],
        "pos_kw": ["stabilize", "strengthen", "appreciate", "peg", "firmed", "gained"],
        "neg_kw": ["devalue", "weaken", "depreciate", "slide", "tumble", "plunged", "fell"],
    },
    EventType.EARNINGS_RELEASE: {
        "keywords": [
            "quarterly results", "annual results", "net profit", "earnings",
            "revenue", "eps", "earnings per share", "financial results",
            "q1", "q2", "q3", "q4", "half year", "full year", "fiscal year",
            "net income", "bottom line",
            "صافي الربح", "الارباح", "الأرباح الفصلية", "نتائج مالية",
            "ايرادات", "الإيرادات",
        ],
        "pos_kw": ["beat", "exceeded", "surged", "grew", "record profit", "strong results",
                   "higher than", "above expectations", "outperformed"],
        "neg_kw": ["missed", "fell", "declined", "loss", "below expectations", "disappointing",
                   "profit warning", "write-down", "impairment"],
    },
    EventType.IMF_WORLD_BANK: {
        "keywords": [
            "imf", "international monetary fund", "world bank", "sba",
            "stand-by arrangement", "disbursement", "tranche", "program review",
            "extended fund facility", "eff", "article iv",
            "صندوق النقد الدولي", "البنك الدولي", "برنامج الاصلاح",
        ],
        "pos_kw": ["approved", "disbursed", "completed review", "on track", "unlocked",
                   "positive assessment"],
        "neg_kw": ["delayed", "suspended", "missed target", "off track", "concern",
                   "structural reform"],
    },
    EventType.MACRO_DATA: {
        "keywords": [
            "inflation", "cpi", "gdp", "trade deficit", "current account",
            "unemployment", "pmi", "purchasing managers", "fiscal", "deficit",
            "budget", "debt", "foreign reserves", "remittances",
            "التضخم", "الناتج المحلي", "عجز الميزانية", "الاحتياطي", "بطالة",
        ],
        "pos_kw": ["fell", "declined", "improved", "beat", "surplus", "grew", "above target"],
        "neg_kw": ["rose", "surged", "worsened", "missed", "widened", "deficit expanded"],
    },
    EventType.REGULATORY_CHANGE: {
        "keywords": [
            "cma", "efsa", "egx regulation", "new rule", "amendment",
            "listing requirement", "disclosure requirement", "fca",
            "heiit al raqaba", "هيئة الرقابة المالية", "البورصة المصرية",
            "قانون", "لائحة", "اشتراطات",
        ],
        "pos_kw": [],
        "neg_kw": [],
    },
    EventType.IPO: {
        "keywords": [
            "ipo", "initial public offering", "listing", "float", "debut",
            "طرح عام", "طرح اولي", "إدراج",
        ],
        "pos_kw": ["oversubscribed", "strong demand", "priced above"],
        "neg_kw": ["undersubscribed", "pulled", "withdrawn", "postponed"],
    },
    EventType.CORPORATE_ACTION: {
        "keywords": [
            "dividend", "merger", "acquisition", "rights issue", "share buyback",
            "capital increase", "spin-off", "takeover", "bid",
            "توزيعات", "ارباح موزعة", "اندماج", "استحواذ", "زيادة رأس المال",
        ],
        "pos_kw": ["dividend raised", "special dividend", "buyback", "premium"],
        "neg_kw": ["dividend cut", "cancelled dividend", "scrip"],
    },
    EventType.GEOPOLITICAL: {
        "keywords": [
            "war", "conflict", "sanctions", "geopolitical", "tension",
            "ceasefire", "peace deal", "escalation", "suez", "red sea",
            "حرب", "نزاع", "عقوبات", "قناة السويس", "البحر الاحمر",
        ],
        "pos_kw": ["ceasefire", "peace", "resolution", "de-escalation"],
        "neg_kw": ["escalation", "attack", "war", "conflict", "disruption"],
    },
}

IRRELEVANT_KEYWORDS = [
    "sports", "football", "soccer", "celebrity", "entertainment",
    "weather", "recipe", "travel", "lifestyle", "fashion",
    "كرة القدم", "رياضة", "ترفيه", "طقس",
]


class EventClassifier:
    """
    Classifies ProcessedChunks into EventType + DriftDirection.
    Uses keyword rules first; falls back to Gemini LLM for ambiguous cases.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        llm_confidence_threshold: float = 0.12,  # Min rule score to skip LLM
    ) -> None:
        self._api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY", "")
        self._llm_threshold = llm_confidence_threshold

    def classify_batch(self, chunks: List[ProcessedChunk]) -> List[ProcessedChunk]:
        return [self._classify_single(chunk) for chunk in chunks]

    def _classify_single(self, chunk: ProcessedChunk) -> ProcessedChunk:
        text = (chunk.title + " " + chunk.content).lower()

        # Hard filter: obvious non-financial content
        if any(kw in text for kw in IRRELEVANT_KEYWORDS):
            chunk.event_type = EventType.IRRELEVANT
            chunk.drift_direction = DriftDirection.NEUTRAL
            return chunk

        # Rule-based classification
        event_type, confidence = self._rule_classify(text)

        if confidence >= self._llm_threshold:
            chunk.event_type = event_type
            chunk.drift_direction = self._classify_direction(text, event_type)
        elif self._api_key:
            event_type, direction = self._llm_classify(chunk)
            chunk.event_type = event_type
            chunk.drift_direction = direction
        else:
            chunk.event_type = EventType.GENERAL
            chunk.drift_direction = DriftDirection.UNCERTAIN

        return chunk

    def _rule_classify(self, text: str) -> Tuple[EventType, float]:
        scores: dict[EventType, float] = {}
        for event_type, rules in CLASSIFICATION_RULES.items():
            matches = sum(1 for kw in rules["keywords"] if kw.lower() in text)
            if matches:
                scores[event_type] = matches / len(rules["keywords"])
        if not scores:
            return EventType.GENERAL, 0.0
        best = max(scores, key=lambda k: scores[k])
        return best, scores[best]

    def _classify_direction(self, text: str, event_type: EventType) -> DriftDirection:
        rules = CLASSIFICATION_RULES.get(event_type, {})
        pos = sum(1 for kw in rules.get("pos_kw", []) if kw.lower() in text)
        neg = sum(1 for kw in rules.get("neg_kw", []) if kw.lower() in text)
        if pos > neg:
            return DriftDirection.POSITIVE
        if neg > pos:
            return DriftDirection.NEGATIVE
        return DriftDirection.UNCERTAIN

    def _llm_classify(self, chunk: ProcessedChunk) -> Tuple[EventType, DriftDirection]:
        """Gemini LLM fallback. Returns (EventType, DriftDirection)."""
        prompt = (
            "You are a financial news classifier for an institutional quantitative "
            "risk platform serving Egypt (EGX) and Saudi Arabia (TASI).\n\n"
            "Classify the article below into exactly ONE event type and ONE drift direction.\n\n"
            "EVENT TYPES: RATE_DECISION, FX_MOVE, EARNINGS_RELEASE, REGULATORY_CHANGE, "
            "MACRO_DATA, IMF_WORLD_BANK, GEOPOLITICAL, CORPORATE_ACTION, IPO, GENERAL, IRRELEVANT\n\n"
            "DRIFT DIRECTION: POSITIVE (good for equities), NEGATIVE (bad), NEUTRAL, UNCERTAIN\n\n"
            f"Title: {chunk.title}\n"
            f"Content: {chunk.content[:600]}\n\n"
            'Respond ONLY with valid JSON: {"event_type":"...","drift_direction":"...","confidence":0.0}'
        )
        try:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            result = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            text = result.text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            return (
                EventType(parsed.get("event_type", "GENERAL")),
                DriftDirection(parsed.get("drift_direction", "UNCERTAIN")),
            )
        except Exception as exc:
            logger.warning("LLM classification failed: %s", exc)
            return EventType.GENERAL, DriftDirection.UNCERTAIN
