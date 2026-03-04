"""
Bull/Bear Evaluation System
Inspired by TradingAgents' Researcher Team (Bull + Bear agents in structured debate).
Adapted for Xmore: deterministic, rule-based scoring — no LLM calls.

The Bull evaluator builds the strongest possible case FOR the majority prediction.
The Bear evaluator builds the strongest possible case AGAINST the majority prediction.
Together they provide a balanced view that catches false confidence and highlights
genuine conviction.
"""

import logging

logger = logging.getLogger(__name__)


def get_majority_prediction(agent_signals):
    """Get the most common prediction among agents."""
    predictions = [s['prediction'] for s in agent_signals]
    if not predictions:
        return "HOLD"
    return max(set(predictions), key=predictions.count)


def build_bull_case(symbol, agent_signals, market_data, sentiment_data):
    """
    Build the strongest possible case FOR the majority prediction.
    Returns a bull_score (0-100) and a list of supporting factors.
    
    Args:
        symbol: Stock ticker (e.g., "COMI.CA")
        agent_signals: List of AgentSignal dicts from all 4 agents
        market_data: Latest price data dict (close, volume, bid, ask, 52w range)
        sentiment_data: Latest sentiment score dict + article count
    
    Returns:
        {
            "bull_score": 0-100,
            "factors": [{"factor": "...", "weight": 0-10, "evidence": "...",
                         "evidence_ar": "..."}, ...],
            "summary": "Brief text summary of the bull case",
            "summary_ar": "Arabic summary"
        }
    """
    majority_direction = get_majority_prediction(agent_signals)
    factors = []
    score = 0
    
    # === FACTOR 1: Agent Agreement (0-25 points) ===
    agreeing = [s for s in agent_signals if s['prediction'] == majority_direction]
    agreement_ratio = len(agreeing) / len(agent_signals) if agent_signals else 0
    
    if agreement_ratio == 1.0:
        score += 25
        factors.append({
            "factor": "unanimous_agreement",
            "weight": 25,
            "evidence": f"All {len(agent_signals)} agents agree: {majority_direction}",
            "evidence_ar": f"جميع {len(agent_signals)} وكلاء متفقون: {majority_direction}"
        })
    elif agreement_ratio >= 0.75:
        score += 18
        factors.append({
            "factor": "strong_majority",
            "weight": 18,
            "evidence": f"{len(agreeing)}/{len(agent_signals)} agents agree: {majority_direction}",
            "evidence_ar": f"{len(agreeing)}/{len(agent_signals)} وكلاء متفقون: {majority_direction}"
        })
    elif agreement_ratio >= 0.5:
        score += 10
        factors.append({
            "factor": "simple_majority",
            "weight": 10,
            "evidence": f"{len(agreeing)}/{len(agent_signals)} agents agree: {majority_direction}",
            "evidence_ar": f"{len(agreeing)}/{len(agent_signals)} وكلاء متفقون: {majority_direction}"
        })
    else:
        score += 3
        factors.append({
            "factor": "minority_signal",
            "weight": 3,
            "evidence": f"Only {len(agreeing)}/{len(agent_signals)} agents agree",
            "evidence_ar": f"فقط {len(agreeing)}/{len(agent_signals)} وكلاء متفقون"
        })
    
    # === FACTOR 2: Average Confidence of Agreeing Agents (0-20 points) ===
    avg_confidence = sum(s['confidence'] for s in agreeing) / len(agreeing) if agreeing else 0
    confidence_score = min(20, int(avg_confidence * 0.2))
    score += confidence_score
    factors.append({
        "factor": "average_confidence",
        "weight": confidence_score,
        "evidence": f"Agreeing agents avg confidence: {avg_confidence:.1f}%",
        "evidence_ar": f"متوسط ثقة الوكلاء المتفقين: {avg_confidence:.1f}%"
    })
    
    # === FACTOR 3: ML Model Probability Strength (0-15 points) ===
    ml_signal = next((s for s in agent_signals if s['agent_name'] == 'ML_RandomForest'), None)
    if ml_signal and ml_signal.get('reasoning', {}).get('class_probabilities'):
        probs = ml_signal['reasoning']['class_probabilities']
        direction_prob = probs.get(majority_direction, 0)
        if direction_prob > 0.70:
            score += 15
            factors.append({
                "factor": "ml_high_probability", "weight": 15,
                "evidence": f"ML model gives {direction_prob:.0%} probability for {majority_direction}",
                "evidence_ar": f"نموذج ML يعطي {direction_prob:.0%} احتمالية لـ {majority_direction}"
            })
        elif direction_prob > 0.55:
            score += 8
            factors.append({
                "factor": "ml_moderate_probability", "weight": 8,
                "evidence": f"ML model gives {direction_prob:.0%} probability",
                "evidence_ar": f"نموذج ML يعطي {direction_prob:.0%} احتمالية"
            })
    
    # === FACTOR 4: Sentiment Alignment (0-10 points) ===
    if sentiment_data:
        sent_score = sentiment_data.get('avg_sentiment', 0)
        sent_label = sentiment_data.get('sentiment_label', 'Neutral')
        article_count = sentiment_data.get('article_count', 0)
        
        sentiment_aligns = (
            (majority_direction == 'UP' and sent_score > 0.1) or
            (majority_direction == 'DOWN' and sent_score < -0.1)
        )
        
        if sentiment_aligns and article_count >= 3:
            score += 10
            factors.append({
                "factor": "sentiment_confirms", "weight": 10,
                "evidence": f"Sentiment ({sent_label}, {sent_score:.2f}) aligns with {majority_direction}, {article_count} articles",
                "evidence_ar": f"المشاعر ({sent_label}، {sent_score:.2f}) تتوافق مع {majority_direction}، {article_count} مقال"
            })
        elif sentiment_aligns:
            score += 5
            factors.append({
                "factor": "weak_sentiment_confirms", "weight": 5,
                "evidence": f"Sentiment aligns but only {article_count} articles — low conviction",
                "evidence_ar": f"المشاعر متوافقة لكن {article_count} مقال فقط — قناعة منخفضة"
            })
    
    # === FACTOR 5: Technical Confirmation (0-15 points) ===
    rsi_signal = next((s for s in agent_signals if s['agent_name'] == 'RSI_Agent'), None)
    ma_signal = next((s for s in agent_signals if s['agent_name'] == 'MA_Crossover_Agent'), None)
    
    if majority_direction == 'UP':
        if rsi_signal and rsi_signal.get('reasoning', {}).get('rsi_value', 50) < 40:
            rsi_val = rsi_signal['reasoning']['rsi_value']
            score += 8
            factors.append({
                "factor": "rsi_confirms_upside", "weight": 8,
                "evidence": f"RSI at {rsi_val:.1f} — room to run",
                "evidence_ar": f"RSI عند {rsi_val:.1f} — مجال للصعود"
            })
        if ma_signal and ma_signal.get('reasoning', {}).get('crossover_type') in ['golden_cross', 'bullish_trend']:
            score += 7
            factors.append({
                "factor": "golden_cross_active", "weight": 7,
                "evidence": "Golden cross (short MA above long MA) — bullish trend",
                "evidence_ar": "تقاطع ذهبي (المتوسط القصير فوق الطويل) — اتجاه صعودي"
            })
    elif majority_direction == 'DOWN':
        if rsi_signal:
            rsi_val = rsi_signal.get('reasoning', {}).get('rsi_value', 50)
            rsi_trend = rsi_signal.get('reasoning', {}).get('rsi_trend', 'flat')
            if rsi_val > 65:
                score += 8
                factors.append({
                    "factor": "rsi_confirms_downside", "weight": 8,
                    "evidence": f"RSI at {rsi_val:.1f} — overbought, room to fall",
                    "evidence_ar": f"RSI عند {rsi_val:.1f} — تشبع شرائي، مجال للهبوط"
                })
            elif rsi_val > 55 and rsi_trend == 'falling':
                score += 5
                factors.append({
                    "factor": "rsi_momentum_bearish", "weight": 5,
                    "evidence": f"RSI at {rsi_val:.1f} and falling — bearish momentum",
                    "evidence_ar": f"RSI عند {rsi_val:.1f} وهابط — زخم هبوطي"
                })
        if ma_signal:
            ct = ma_signal.get('reasoning', {}).get('crossover_type', '')
            if ct in ['death_cross', 'bearish_trend', 'bearish_slope_override']:
                score += 7
                factors.append({
                    "factor": "death_cross_active", "weight": 7,
                    "evidence": "Death cross or declining MA trend — bearish",
                    "evidence_ar": "تقاطع الموت أو اتجاه المتوسط الهابط — هبوطي"
                })
            elif ma_signal.get('reasoning', {}).get('ma_slope_bearish'):
                score += 4
                factors.append({
                    "factor": "ma_slope_declining", "weight": 4,
                    "evidence": "Both MAs declining — underlying bearish momentum",
                    "evidence_ar": "كلا المتوسطين هابطان — زخم هبوطي أساسي"
                })
    
    # === FACTOR 6: Volume Confirmation (0-10 points) ===
    vol_signal = next((s for s in agent_signals if s['agent_name'] == 'Volume_Spike_Agent'), None)
    if vol_signal and vol_signal.get('reasoning', {}).get('is_spike'):
        price_dir = vol_signal['reasoning'].get('price_direction_on_spike', '')
        vol_ratio = vol_signal['reasoning'].get('volume_ratio', 1.0)
        if (majority_direction == 'UP' and price_dir == 'up') or \
           (majority_direction == 'DOWN' and price_dir == 'down'):
            score += 10
            factors.append({
                "factor": "volume_confirms_direction", "weight": 10,
                "evidence": f"Volume spike ({vol_ratio:.1f}x avg) confirms {majority_direction} move",
                "evidence_ar": f"ارتفاع الحجم ({vol_ratio:.1f}x المتوسط) يؤكد حركة {majority_direction}"
            })
    
    # === FACTOR 7: 52-Week Range Position (0-5 points) ===
    if market_data and market_data.get('range_52w_position') is not None:
        pos = market_data['range_52w_position']
        if majority_direction == 'UP' and pos < 0.3:
            score += 5
            factors.append({
                "factor": "near_52w_low", "weight": 5,
                "evidence": f"Stock at {pos:.0%} of 52-week range — near low, upside room",
                "evidence_ar": f"السهم عند {pos:.0%} من نطاق 52 أسبوع — قرب القاع، مجال للصعود"
            })
        elif majority_direction == 'DOWN' and pos > 0.8:
            score += 5
            factors.append({
                "factor": "near_52w_high", "weight": 5,
                "evidence": f"Stock at {pos:.0%} of 52-week range — near high, downside risk",
                "evidence_ar": f"السهم عند {pos:.0%} من نطاق 52 أسبوع — قرب القمة، خطر هبوط"
            })
    
    score = min(100, score)
    
    summary = _generate_bull_summary(majority_direction, score, factors)
    summary_ar = _generate_bull_summary_ar(majority_direction, score, factors)
    
    return {
        "bull_score": score,
        "factors": sorted(factors, key=lambda f: f['weight'], reverse=True),
        "summary": summary,
        "summary_ar": summary_ar
    }


def build_bear_case(symbol, agent_signals, market_data, sentiment_data, historical_accuracy=None):
    """
    Build the strongest possible case AGAINST the majority prediction.
    The bear case looks for reasons the signal might be WRONG.
    
    Returns: {"bear_score": 0-100, "factors": [...], "summary": "...", "summary_ar": "..."}
    """
    majority_direction = get_majority_prediction(agent_signals)
    factors = []
    score = 0
    
    agreeing = [s for s in agent_signals if s['prediction'] == majority_direction]
    dissenting = [s for s in agent_signals if s['prediction'] != majority_direction]
    
    # === RISK 1: Low Agent Agreement (0-20 points) ===
    if len(dissenting) >= 2:
        score += 20
        dissent_agents = [d['agent_name'] for d in dissenting]
        factors.append({
            "factor": "high_disagreement", "weight": 20,
            "evidence": f"{len(dissenting)} agents disagree: {', '.join(dissent_agents)}",
            "evidence_ar": f"{len(dissenting)} وكلاء يختلفون: {', '.join(dissent_agents)}"
        })
    elif len(dissenting) == 1:
        if dissenting[0]['agent_name'] == 'ML_RandomForest':
            score += 15
            factors.append({
                "factor": "ml_model_dissents", "weight": 15,
                "evidence": "ML_RandomForest (typically most accurate) disagrees with majority",
                "evidence_ar": "نموذج ML (الأكثر دقة عادةً) يختلف مع الأغلبية"
            })
        else:
            score += 8
            factors.append({
                "factor": "single_dissenter", "weight": 8,
                "evidence": f"{dissenting[0]['agent_name']} disagrees",
                "evidence_ar": f"{dissenting[0]['agent_name']} يختلف"
            })
    
    # === RISK 2: Low Confidence (0-15 points) ===
    avg_confidence = sum(s['confidence'] for s in agreeing) / len(agreeing) if agreeing else 50
    if avg_confidence < 55:
        score += 15
        factors.append({
            "factor": "low_confidence", "weight": 15,
            "evidence": f"Agreeing agents avg confidence only {avg_confidence:.1f}% — weak conviction",
            "evidence_ar": f"متوسط ثقة الوكلاء المتفقين {avg_confidence:.1f}% فقط — قناعة ضعيفة"
        })
    elif avg_confidence < 65:
        score += 8
        factors.append({
            "factor": "moderate_confidence", "weight": 8,
            "evidence": f"Agreeing agents avg confidence {avg_confidence:.1f}% — not strong",
            "evidence_ar": f"متوسط ثقة الوكلاء {avg_confidence:.1f}% — ليست قوية"
        })
    
    # === RISK 3: Sentiment Contradicts Signal (0-15 points) ===
    if sentiment_data:
        sent_score = sentiment_data.get('avg_sentiment', 0)
        sentiment_contradicts = (
            (majority_direction == 'UP' and sent_score < -0.15) or
            (majority_direction == 'DOWN' and sent_score > 0.15)
        )
        if sentiment_contradicts:
            score += 15
            factors.append({
                "factor": "sentiment_contradicts", "weight": 15,
                "evidence": f"Market sentiment ({sent_score:.2f}) opposes {majority_direction} signal",
                "evidence_ar": f"مشاعر السوق ({sent_score:.2f}) تعارض إشارة {majority_direction}"
            })
    
    # === RISK 4: Historical Agent Accuracy (0-15 points) ===
    if historical_accuracy:
        stock_accuracy = historical_accuracy.get(symbol, {})
        if stock_accuracy:
            avg_stock_accuracy = sum(stock_accuracy.values()) / len(stock_accuracy)
            if avg_stock_accuracy < 0.45:
                score += 15
                factors.append({
                    "factor": "poor_historical_accuracy", "weight": 15,
                    "evidence": f"Agents historically only {avg_stock_accuracy:.0%} accurate on {symbol}",
                    "evidence_ar": f"الوكلاء تاريخياً بدقة {avg_stock_accuracy:.0%} فقط على {symbol}"
                })
            elif avg_stock_accuracy < 0.55:
                score += 8
                factors.append({
                    "factor": "mediocre_historical_accuracy", "weight": 8,
                    "evidence": f"Agents historically {avg_stock_accuracy:.0%} accurate on {symbol} — no edge",
                    "evidence_ar": f"الوكلاء تاريخياً بدقة {avg_stock_accuracy:.0%} على {symbol} — لا ميزة"
                })
    
    # === RISK 5: RSI Exhaustion (0-10 points) ===
    rsi_signal = next((s for s in agent_signals if s['agent_name'] == 'RSI_Agent'), None)
    if rsi_signal:
        rsi_val = rsi_signal.get('reasoning', {}).get('rsi_value', 50)
        if majority_direction == 'UP' and rsi_val > 70:
            score += 10
            factors.append({
                "factor": "rsi_overbought", "weight": 10,
                "evidence": f"RSI at {rsi_val:.1f} — already overbought, UP may be too late",
                "evidence_ar": f"RSI عند {rsi_val:.1f} — تشبع شرائي، الصعود قد يكون متأخراً"
            })
        elif majority_direction == 'DOWN' and rsi_val < 30:
            score += 10
            factors.append({
                "factor": "rsi_oversold", "weight": 10,
                "evidence": f"RSI at {rsi_val:.1f} — already oversold, DOWN may be exhausted",
                "evidence_ar": f"RSI عند {rsi_val:.1f} — تشبع بيعي، الهبوط قد يكون منهكاً"
            })
    
    # === RISK 6: Volume Divergence (0-10 points) ===
    vol_signal = next((s for s in agent_signals if s['agent_name'] == 'Volume_Spike_Agent'), None)
    if vol_signal:
        vol_ratio = vol_signal.get('reasoning', {}).get('volume_ratio', 1.0)
        if majority_direction in ('UP', 'DOWN') and vol_ratio < 0.7:
            score += 10
            factors.append({
                "factor": "low_volume", "weight": 10,
                "evidence": f"Volume at {vol_ratio:.1f}x avg — no conviction behind the move",
                "evidence_ar": f"الحجم عند {vol_ratio:.1f}x المتوسط — لا قناعة وراء الحركة"
            })
    
    # === RISK 7: Extreme 52-Week Position (0-10 points) ===
    if market_data and market_data.get('range_52w_position') is not None:
        pos = market_data['range_52w_position']
        if majority_direction == 'UP' and pos > 0.9:
            score += 10
            factors.append({
                "factor": "near_52w_high_resistance", "weight": 10,
                "evidence": f"Stock at {pos:.0%} of 52-week range — UP faces resistance",
                "evidence_ar": f"السهم عند {pos:.0%} من نطاق 52 أسبوع — الصعود يواجه مقاومة"
            })
        elif majority_direction == 'DOWN' and pos < 0.1:
            score += 10
            factors.append({
                "factor": "near_52w_low_support", "weight": 10,
                "evidence": f"Stock at {pos:.0%} of 52-week range — DOWN faces support",
                "evidence_ar": f"السهم عند {pos:.0%} من نطاق 52 أسبوع — الهبوط يواجه دعم"
            })
    
    # === RISK 8: ML Model Uncertainty (0-5 points) ===
    ml_signal = next((s for s in agent_signals if s['agent_name'] == 'ML_RandomForest'), None)
    if ml_signal and ml_signal.get('reasoning', {}).get('class_probabilities'):
        probs = ml_signal['reasoning']['class_probabilities']
        max_prob = max(probs.values()) if probs else 0.5
        if max_prob < 0.45:
            score += 5
            factors.append({
                "factor": "ml_uncertain", "weight": 5,
                "evidence": f"ML model max probability only {max_prob:.0%} — high uncertainty",
                "evidence_ar": f"أقصى احتمالية لنموذج ML هي {max_prob:.0%} فقط — عدم يقين عالي"
            })
    
    score = min(100, score)
    
    summary = _generate_bear_summary(majority_direction, score, factors)
    summary_ar = _generate_bear_summary_ar(majority_direction, score, factors)
    
    return {
        "bear_score": score,
        "factors": sorted(factors, key=lambda f: f['weight'], reverse=True),
        "summary": summary,
        "summary_ar": summary_ar
    }


def _generate_bull_summary(direction, score, factors):
    """Generate a human-readable bull case summary."""
    top_factors = [f['factor'].replace('_', ' ') for f in factors[:3]]
    strength = "Strong" if score >= 70 else "Moderate" if score >= 45 else "Weak"
    return f"{strength} bull case for {direction} ({score}/100). Key: {', '.join(top_factors)}"


def _generate_bull_summary_ar(direction, score, factors):
    direction_map = {"UP": "صعود", "DOWN": "هبوط", "HOLD": "انتظار", "FLAT": "محايد"}
    dir_ar = direction_map.get(direction, direction)
    strength = "قوية" if score >= 70 else "متوسطة" if score >= 45 else "ضعيفة"
    return f"حالة صعود {strength} لـ {dir_ar} ({score}/100)"


def _generate_bear_summary(direction, score, factors):
    top_factors = [f['factor'].replace('_', ' ') for f in factors[:3]]
    risk_level = "High" if score >= 60 else "Moderate" if score >= 35 else "Low"
    return f"{risk_level} risk against {direction} ({score}/100). Concerns: {', '.join(top_factors)}"


def _generate_bear_summary_ar(direction, score, factors):
    direction_map = {"UP": "صعود", "DOWN": "هبوط", "HOLD": "انتظار", "FLAT": "محايد"}
    dir_ar = direction_map.get(direction, direction)
    risk_level = "عالية" if score >= 60 else "متوسطة" if score >= 35 else "منخفضة"
    return f"مخاطر {risk_level} ضد {dir_ar} ({score}/100)"
