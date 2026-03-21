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
    Map numeric scores to a conviction label and Xmore Score (0-100).

    Returns (conviction_label, xmore_score).
    xmore_score is a continuous 0-100 composite used as a comparable rank metric.
    """
    # Weighted composite — same formula used for conviction gating
    composite = (
        bull_score * 0.30 +
        (100 - bear_score) * 0.25 +
        agreement_ratio * 100 * 0.25 +
        avg_confidence * 0.20
    )
    xmore_score = round(max(0.0, min(100.0, composite)), 1)

    if composite >= 75:
        return "VERY_HIGH", xmore_score
    elif composite >= 60:
        return "HIGH", xmore_score
    elif composite >= 40:
        return "MODERATE", xmore_score
    else:
        return "LOW", xmore_score


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

def _apply_regime_gate(signal: str, conviction: str,
                       market_regime: Optional[Dict[str, Any]]) -> tuple:
    """
    Layer 4: Market regime filter applied after risk gating.

    Rules (hard suppression — directional signals are too unreliable in
    elevated-volatility regimes to justify active trading):

      Crisis   (highest-vol HMM state, confidence >= 60%):
        - UP  → HOLD  (crisis regime invalidates bullish bets)
        - DOWN → HOLD  (whipsaw risk too high; stay flat)

      Turbulent (mid-vol state, confidence >= 60%):
        - UP  → HOLD  (volatility erodes signal edge)
        - DOWN → HOLD  (EGX has limited short-selling; downside moves are
                        unpredictable in turbulent conditions)

      Calm: no adjustment.

    Returns (adjusted_signal, adjusted_conviction, regime_flag_str_or_None).
    """
    if not market_regime:
        return signal, conviction, None

    label = market_regime.get('regime_label_en', 'Calm')
    confidence = float(market_regime.get('regime_confidence', 0.0))

    flag = None

    if label == 'Crisis' and confidence >= 0.60:
        if signal in ('UP', 'DOWN'):
            flag = f"{signal} blocked: Crisis regime ({confidence:.0%} confidence)"
            signal = 'HOLD'
            conviction = 'LOW'

    elif label == 'Turbulent' and confidence >= 0.60:
        if signal in ('UP', 'DOWN'):
            flag = f"{signal} blocked: Turbulent regime ({confidence:.0%} confidence)"
            signal = 'HOLD'
            conviction = 'LOW'

    return signal, conviction, flag


def run_consensus(symbol: str,
                  agent_signals: List[Dict[str, Any]],
                  market_data: Optional[Dict[str, Any]] = None,
                  sentiment_data: Optional[Dict[str, Any]] = None,
                  historical_accuracy: Optional[Dict] = None,
                  portfolio_signals: Optional[List[Dict[str, Any]]] = None,
                  risk_config: Optional[Dict[str, Any]] = None,
                  dynamic_weights: Optional[Dict[str, float]] = None,
                  market_regime: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Full 4-layer consensus pipeline for a single stock.

    Layers:
      1. Signal Agents     — individual structured predictions (passed in)
      2. Bull/Bear         — construct cases for/against majority direction
      3. Risk Gating       — evaluate_risk() blocks/downgrades dangerous signals
      4. Regime Filter     — HMM market regime blocks ALL directional signals in Crisis/Turbulent

    Args:
        symbol:              Stock ticker (e.g. "COMI.CA")
        agent_signals:       List of AgentSignal dicts (from Layer 1)
        market_data:         Dict with price, volume, volatility, drawdowns, 52w range
        sentiment_data:      Dict with avg_sentiment, sentiment_label, article_count
        historical_accuracy: Dict mapping symbol -> {agent_name: accuracy}
        portfolio_signals:   List of already-decided signals this run
        risk_config:         Override risk thresholds
        dynamic_weights:     Accuracy-adjusted agent weights
        market_regime:       RegimeState.to_dict() from _detect_market_regime()

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

    conviction, xmore_score = _compute_conviction(
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

    # ── Layer 4: Market Regime Filter ──
    regime_flag = None
    if market_regime:
        final_signal, final_conviction, regime_flag = _apply_regime_gate(
            final_signal, final_conviction, market_regime
        )
        if regime_flag:
            logger.info(f"[{symbol}] Regime gate: {regime_flag}")

    # ── Build Reasoning Chain ──
    reasoning_chain = _build_reasoning_chain(
        symbol, agent_signals, consensus_signal, bull_case, bear_case,
        risk_assessment, final_signal, final_conviction,
        market_regime=market_regime, regime_flag=regime_flag
    )

    # ── Build Display Text ──
    display = _build_display(
        symbol, final_signal, final_conviction,
        bull_case, bear_case, risk_assessment, agreement_ratio,
        market_regime=market_regime, regime_flag=regime_flag
    )

    # ── Assemble Final Result ──
    agreeing_count = sum(1 for s in agent_signals
                         if s['prediction'] == get_majority_prediction(agent_signals))

    result = {
        "symbol": symbol,
        "timestamp": timestamp,

        # Final output
        "final_signal": final_signal,
        "conviction": final_conviction,
        "confidence": round(weighted_confidence, 1),
        "xmore_score": xmore_score,
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

        # Regime
        "market_regime": market_regime,
        "regime_flag": regime_flag,

        # Individual signals
        "agent_signals": agent_signals,

        # Narrative
        "reasoning_chain": reasoning_chain,
        "display": display
    }

    logger.info(
        f"[{symbol}] Consensus: {final_signal} ({final_conviction}) | "
        f"Bull={bull_case['bull_score']} Bear={bear_case['bear_score']} | "
        f"Risk={risk_assessment['action']} ({risk_assessment['risk_score']}) | "
        f"Regime={market_regime.get('regime_label_en', 'N/A') if market_regime else 'N/A'}"
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
        "xmore_score": 0.0,
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
                           final_signal, final_conviction,
                           market_regime=None, regime_flag=None):
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

    # Step 6: Regime filter
    if market_regime:
        chain.append({
            "step": "regime_filter",
            "regime": market_regime.get('regime_label_en', 'Calm'),
            "confidence": round(market_regime.get('regime_confidence', 0), 3),
            "adjusted": regime_flag is not None,
            "flag": regime_flag or "no adjustment"
        })

    # Step 7: Final output
    chain.append({
        "step": "final_output",
        "signal": final_signal,
        "conviction": final_conviction
    })

    return chain


def _build_display(symbol, final_signal, final_conviction,
                   bull_case, bear_case, risk_assessment, agreement_ratio,
                   market_regime=None, regime_flag=None):
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

    risk_action = risk_assessment.get('action', 'PASS')
    bull_s = bull_case['bull_score']
    bear_s = bear_case['bear_score']

    # Regime suffix for summary
    regime_suffix_en = ''
    regime_suffix_ar = ''
    if market_regime:
        lbl = market_regime.get('regime_label_en', '')
        if lbl in ('Turbulent', 'Crisis'):
            lbl_ar = market_regime.get('regime_label_ar', lbl)
            regime_suffix_en = f" Regime: {lbl}."
            regime_suffix_ar = f" النظام: {lbl_ar}."

    if regime_flag and 'blocked' in regime_flag:
        regime_lbl = market_regime.get('regime_label_en', '') if market_regime else ''
        regime_lbl_ar = market_regime.get('regime_label_ar', regime_lbl) if market_regime else ''
        summary_en = f"Signal held: {regime_lbl} market regime — directional bets suppressed. Bull: {bull_s} vs Bear: {bear_s}."
        summary_ar = f"إشارة محتجزة: نظام السوق {regime_lbl_ar} — إشارات الاتجاه مكبوتة. الثور: {bull_s} مقابل الدب: {bear_s}."
    elif risk_action == "BLOCK":
        summary_en = f"Signal blocked by Risk Agent. Bull: {bull_s}, Bear: {bear_s}.{regime_suffix_en}"
        summary_ar = f"الإشارة محظورة من وكيل المخاطر. الثور: {bull_s}، الدب: {bear_s}.{regime_suffix_ar}"
    elif risk_action == "DOWNGRADE":
        summary_en = f"{sig['en']} downgraded (risk). Bull: {bull_s} vs Bear: {bear_s}.{regime_suffix_en}"
        summary_ar = f"إشارة {sig['ar']} مخفضة (مخاطر). الثور: {bull_s} مقابل الدب: {bear_s}.{regime_suffix_ar}"
    elif risk_action == "FLAG":
        summary_en = f"{sig['en']} ({conv}) with caution. Bull: {bull_s} vs Bear: {bear_s}. {agreement_ratio:.0%} agree.{regime_suffix_en}"
        summary_ar = f"{sig['ar']} ({conv_ar}) مع تحفظات. الثور: {bull_s} مقابل الدب: {bear_s}. {agreement_ratio:.0%} متفقون.{regime_suffix_ar}"
    else:
        summary_en = f"{sig['en']} ({conv}). Bull: {bull_s} vs Bear: {bear_s}. {agreement_ratio:.0%} agree.{regime_suffix_en}"
        summary_ar = f"{sig['ar']} ({conv_ar}). الثور: {bull_s} مقابل الدب: {bear_s}. {agreement_ratio:.0%} متفقون.{regime_suffix_ar}"

    return {
        "signal_text": sig['en'],
        "signal_text_ar": sig['ar'],
        "conviction_text": conv,
        "conviction_text_ar": conv_ar,
        "summary": summary_en,
        "summary_ar": summary_ar
    }
