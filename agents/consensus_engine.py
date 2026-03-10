"""
Consensus Engine — 3-Layer Orchestrator.

Orchestrates:
  Layer 1: Signal Agents  →  collect structured predictions
  Layer 2: Bull/Bear      →  build cases FOR and AGAINST the majority
  Layer 3: Risk Agent     →  gate the final output

Produces a single, risk-adjusted consensus signal per stock with
full reasoning chain and bilingual display text.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from agents.bull_bear_evaluator import build_bull_case, build_bear_case, get_majority_prediction
from agents.risk_agent import evaluate_risk

logger = logging.getLogger(__name__)


# ============================================
# CONVICTION MAPPING
# ============================================

def _compute_conviction(bull_score, bear_score, agreement_ratio, avg_confidence):
    """
    Map numeric scores to a conviction label.
    
    Returns one of: VERY_HIGH, HIGH, MODERATE, LOW
    """
    # Weighted composite
    composite = (
        bull_score * 0.30 +
        (100 - bear_score) * 0.25 +
        agreement_ratio * 100 * 0.25 +
        avg_confidence * 0.20
    )
    
    if composite >= 75:
        return "VERY_HIGH"
    elif composite >= 60:
        return "HIGH"
    elif composite >= 40:
        return "MODERATE"
    else:
        return "LOW"


def _conviction_display(conviction, lang='en'):
    """Bilingual conviction labels."""
    labels = {
        "VERY_HIGH": {"en": "Very High", "ar": "عالية جداً"},
        "HIGH":      {"en": "High",      "ar": "عالية"},
        "MODERATE":  {"en": "Moderate",   "ar": "متوسطة"},
        "LOW":       {"en": "Low",        "ar": "منخفضة"},
        "BLOCKED":   {"en": "Blocked",    "ar": "محظور"},
    }
    return labels.get(conviction, labels["LOW"]).get(lang, conviction)


# ============================================
# WEIGHTED CONSENSUS
# ============================================

AGENT_WEIGHTS = {
    "ML_RandomForest":     0.35,
    "MA_Crossover_Agent":  0.25,
    "RSI_Agent":           0.20,
    "Volume_Spike_Agent":  0.20,
}


def _weighted_consensus(agent_signals, dynamic_weights=None):
    """
    Compute weighted vote across agent signals.
    Returns (signal, weighted_confidence, agreement_ratio).

    dynamic_weights: optional dict mapping agent_name → weight (accuracy-adjusted).
                     Falls back to module-level AGENT_WEIGHTS if None.
    """
    if not agent_signals:
        return "HOLD", 0.0, 0.0

    weights = dynamic_weights if dynamic_weights else AGENT_WEIGHTS

    direction_scores = {"UP": 0.0, "DOWN": 0.0, "HOLD": 0.0, "FLAT": 0.0}
    total_weight = 0.0

    for sig in agent_signals:
        agent_name = sig.get('agent_name', '')
        weight = weights.get(agent_name, 0.20)
        confidence = sig.get('confidence', 50) / 100.0
        prediction = sig.get('prediction', 'HOLD')

        direction_scores[prediction] = direction_scores.get(prediction, 0) + (weight * confidence)
        total_weight += weight
    
    # Normalize FLAT → HOLD
    direction_scores["HOLD"] += direction_scores.pop("FLAT", 0)
    
    # Winner
    best_direction = max(direction_scores, key=direction_scores.get)
    best_score = direction_scores[best_direction]
    weighted_confidence = (best_score / total_weight * 100) if total_weight > 0 else 50.0
    
    # Agreement ratio
    majority = get_majority_prediction(agent_signals)
    agreeing = sum(1 for s in agent_signals if s['prediction'] == majority)
    agreement_ratio = agreeing / len(agent_signals) if agent_signals else 0
    
    return best_direction, weighted_confidence, agreement_ratio


# ============================================
# MAIN ENGINE
# ============================================

def run_consensus(symbol: str,
                  agent_signals: List[Dict[str, Any]],
                  market_data: Optional[Dict[str, Any]] = None,
                  sentiment_data: Optional[Dict[str, Any]] = None,
                  historical_accuracy: Optional[Dict] = None,
                  portfolio_signals: Optional[List[Dict[str, Any]]] = None,
                  risk_config: Optional[Dict[str, Any]] = None,
                  dynamic_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Full 3-layer consensus pipeline for a single stock.
    
    Args:
        symbol:              Stock ticker (e.g. "COMI.CA")
        agent_signals:       List of AgentSignal dicts (from Layer 1)
        market_data:         Dict with price, volume, volatility, drawdowns, 52w range
        sentiment_data:      Dict with avg_sentiment, sentiment_label, article_count
        historical_accuracy: Dict mapping symbol → {agent_name: accuracy}
        portfolio_signals:   List of already-decided signals this run
        risk_config:         Override risk thresholds
    
    Returns:
        Comprehensive consensus result dictionary.
    """
    timestamp = datetime.utcnow().isoformat()
    
    if not agent_signals:
        return _empty_result(symbol, timestamp)
    
    # ── Layer 1: Already done — signals are passed in ──
    
    # ── Layer 2: Bull / Bear Evaluation ──
    bull_case = build_bull_case(symbol, agent_signals, market_data, sentiment_data)
    bear_case = build_bear_case(symbol, agent_signals, market_data, sentiment_data,
                                historical_accuracy)
    
    # ── Weighted Consensus ──
    consensus_signal, weighted_confidence, agreement_ratio = _weighted_consensus(
        agent_signals, dynamic_weights=dynamic_weights
    )
    
    avg_confidence = sum(s.get('confidence', 50) for s in agent_signals) / len(agent_signals)
    
    conviction = _compute_conviction(
        bull_case['bull_score'], bear_case['bear_score'],
        agreement_ratio, avg_confidence
    )
    
    # ── Layer 3: Risk Gating ──
    pre_risk_result = {
        "final_signal": consensus_signal,
        "bull_score": bull_case['bull_score'],
        "bear_score": bear_case['bear_score'],
        "agent_agreement": agreement_ratio,
        "conviction": conviction,
        "confidence": weighted_confidence
    }
    
    risk_assessment = evaluate_risk(
        symbol, pre_risk_result,
        market_data=market_data,
        portfolio_signals=portfolio_signals,
        risk_config=risk_config
    )
    
    final_signal = risk_assessment['adjusted_signal']
    final_conviction = risk_assessment['adjusted_conviction']
    
    # ── Build Reasoning Chain ──
    reasoning_chain = _build_reasoning_chain(
        symbol, agent_signals, consensus_signal, bull_case, bear_case,
        risk_assessment, final_signal, final_conviction
    )
    
    # ── Build Display Text ──
    display = _build_display(
        symbol, final_signal, final_conviction,
        bull_case, bear_case, risk_assessment, agreement_ratio
    )
    
    # ── Assemble Final Result ──
    agreeing_count = sum(1 for s in agent_signals if s['prediction'] == get_majority_prediction(agent_signals))
    
    result = {
        "symbol": symbol,
        "timestamp": timestamp,
        
        # Final output
        "final_signal": final_signal,
        "conviction": final_conviction,
        "confidence": round(weighted_confidence, 1),
        "risk_adjusted": risk_assessment['action'] != "PASS",
        
        # Agreement
        "agent_agreement": round(agreement_ratio, 2),
        "agents_agreeing": agreeing_count,
        "agents_total": len(agent_signals),
        "majority_direction": get_majority_prediction(agent_signals),
        
        # Bull / Bear
        "bull_score": bull_case['bull_score'],
        "bear_score": bear_case['bear_score'],
        "bull_case": bull_case,
        "bear_case": bear_case,
        
        # Risk
        "risk_assessment": risk_assessment,
        "risk_action": risk_assessment['action'],
        "risk_score": risk_assessment['risk_score'],
        
        # Individual signals
        "agent_signals": agent_signals,
        
        # Narrative
        "reasoning_chain": reasoning_chain,
        "display": display
    }
    
    logger.info(
        f"[{symbol}] Consensus: {final_signal} ({final_conviction}) | "
        f"Bull={bull_case['bull_score']} Bear={bear_case['bear_score']} | "
        f"Risk={risk_assessment['action']} ({risk_assessment['risk_score']})"
    )
    
    return result


def _empty_result(symbol, timestamp):
    """Return an empty consensus result when no signals are available."""
    return {
        "symbol": symbol,
        "timestamp": timestamp,
        "final_signal": "HOLD",
        "conviction": "LOW",
        "confidence": 0.0,
        "risk_adjusted": False,
        "agent_agreement": 0,
        "agents_agreeing": 0,
        "agents_total": 0,
        "majority_direction": "HOLD",
        "bull_score": 0,
        "bear_score": 0,
        "bull_case": {"bull_score": 0, "factors": [], "summary": "No signals", "summary_ar": "لا إشارات"},
        "bear_case": {"bear_score": 0, "factors": [], "summary": "No signals", "summary_ar": "لا إشارات"},
        "risk_assessment": {
            "action": "PASS", "original_signal": "HOLD", "adjusted_signal": "HOLD",
            "original_conviction": "LOW", "adjusted_conviction": "LOW",
            "risk_flags": [], "risk_flags_ar": [], "risk_score": 0, "details": {}
        },
        "risk_action": "PASS",
        "risk_score": 0,
        "agent_signals": [],
        "reasoning_chain": [],
        "display": {
            "signal_text": "Hold", "signal_text_ar": "انتظار",
            "conviction_text": "Low", "conviction_text_ar": "منخفضة",
            "summary": "No agent signals available.", "summary_ar": "لا توجد إشارات من الوكلاء."
        }
    }


def _build_reasoning_chain(symbol, agent_signals, consensus_signal,
                           bull_case, bear_case, risk_assessment,
                           final_signal, final_conviction):
    """Build a step-by-step reasoning chain for transparency."""
    chain = []
    
    # Step 1: Individual signals
    for sig in agent_signals:
        chain.append({
            "step": "agent_signal",
            "agent": sig.get('agent_name', ''),
            "prediction": sig.get('prediction', 'HOLD'),
            "confidence": sig.get('confidence', 0),
        })
    
    # Step 2: Weighted consensus
    chain.append({
        "step": "weighted_consensus",
        "result": consensus_signal,
        "note": f"Weighted vote across {len(agent_signals)} agents"
    })
    
    # Step 3: Bull case
    chain.append({
        "step": "bull_evaluation",
        "score": bull_case['bull_score'],
        "top_factors": [f['factor'] for f in bull_case['factors'][:3]]
    })
    
    # Step 4: Bear case
    chain.append({
        "step": "bear_evaluation",
        "score": bear_case['bear_score'],
        "top_factors": [f['factor'] for f in bear_case['factors'][:3]]
    })
    
    # Step 5: Risk gate
    chain.append({
        "step": "risk_gate",
        "action": risk_assessment['action'],
        "risk_score": risk_assessment['risk_score'],
        "flags_count": len(risk_assessment['risk_flags']),
        "adjusted": risk_assessment['action'] != "PASS"
    })
    
    # Step 6: Final output
    chain.append({
        "step": "final_output",
        "signal": final_signal,
        "conviction": final_conviction
    })
    
    return chain


def _build_display(symbol, final_signal, final_conviction,
                   bull_case, bear_case, risk_assessment, agreement_ratio):
    """Build bilingual display text for the dashboard."""
    signal_map = {
        "UP":   {"en": "Bullish", "ar": "صاعد"},
        "DOWN": {"en": "Bearish", "ar": "هابط"},
        "HOLD": {"en": "Hold",    "ar": "انتظار"},
        "FLAT": {"en": "Neutral", "ar": "محايد"},
    }
    
    sig = signal_map.get(final_signal, signal_map["HOLD"])
    conv = _conviction_display(final_conviction, 'en')
    conv_ar = _conviction_display(final_conviction, 'ar')
    
    # Build summary
    risk_action = risk_assessment.get('action', 'PASS')
    bull_s = bull_case['bull_score']
    bear_s = bear_case['bear_score']
    
    if risk_action == "BLOCK":
        summary_en = f"Signal blocked by Risk Agent. Bull: {bull_s}, Bear: {bear_s}."
        summary_ar = f"الإشارة محظورة من وكيل المخاطر. الثور: {bull_s}، الدب: {bear_s}."
    elif risk_action == "DOWNGRADE":
        summary_en = f"{sig['en']} signal downgraded due to risk. Bull: {bull_s} vs Bear: {bear_s}."
        summary_ar = f"إشارة {sig['ar']} مخفضة بسبب المخاطر. الثور: {bull_s} مقابل الدب: {bear_s}."
    elif risk_action == "FLAG":
        summary_en = f"{sig['en']} ({conv}) with caution. Bull: {bull_s} vs Bear: {bear_s}. {agreement_ratio:.0%} agents agree."
        summary_ar = f"{sig['ar']} ({conv_ar}) مع تحفظات. الثور: {bull_s} مقابل الدب: {bear_s}. {agreement_ratio:.0%} وكلاء متفقون."
    else:
        summary_en = f"{sig['en']} ({conv}). Bull: {bull_s} vs Bear: {bear_s}. {agreement_ratio:.0%} agents agree."
        summary_ar = f"{sig['ar']} ({conv_ar}). الثور: {bull_s} مقابل الدب: {bear_s}. {agreement_ratio:.0%} وكلاء متفقون."
    
    return {
        "signal_text": sig['en'],
        "signal_text_ar": sig['ar'],
        "conviction_text": conv,
        "conviction_text_ar": conv_ar,
        "summary": summary_en,
        "summary_ar": summary_ar
    }
