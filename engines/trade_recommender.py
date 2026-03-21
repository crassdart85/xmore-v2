"""
Trade Recommendation Engine
Translates consensus signals + user positions into BUY/SELL/HOLD/WATCH actions.
"""

from datetime import date, datetime

TRADE_CONFIG = {
    # Minimum thresholds to trigger BUY
    "buy_min_confidence": 60,           # Consensus confidence >= 60%
    "buy_min_conviction": "MEDIUM",     # At least MEDIUM conviction
    "buy_allowed_risk_actions": ["PASS", "FLAG"],  # Don't buy on DOWNGRADE/BLOCK
    "buy_min_bull_score": 50,           # Bull case must score >= 50/100
    "buy_max_bear_score": 60,           # Bear case must be <= 60/100
    
    # Triggers to recommend SELL
    "sell_on_reversal": True,           # Sell if signal flips opposite to position
    "sell_on_downgrade": True,          # Sell if Risk_Agent DOWNGRADEs
    "sell_on_low_confidence": 35,       # Sell if confidence drops below 35%
    "sell_on_conviction_drop": "LOW",   # Sell if conviction drops to LOW
    "sell_on_bear_dominance": 70,       # Sell if bear_score exceeds 70
    
    # HOLD conditions
    "hold_min_confidence": 40,          # Keep holding if confidence >= 40%
    
    # Position limits
    "max_open_positions": 5,            # Max simultaneous positions per user (free tier)
    "max_open_positions_pro": 15,       # Pro tier
    
    # Cooldown: Don't BUY a stock you just SOLD within N days
    "cooldown_days": 2,
}

CONVICTION_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

from engines.trade_translator import translate_reasons

def _today():
    return date.today()

def _days_between(date1, date2):
    """Calculate days between two dates."""
    if isinstance(date1, str):
        date1 = datetime.strptime(date1, "%Y-%m-%d").date()
    if isinstance(date2, str):
        date2 = datetime.strptime(date2, "%Y-%m-%d").date()
    return (date2 - date1).days

def _in_cooldown(symbol, recent_trades, cooldown_days):
    """Check if stock was recently SOLD and is in cooldown."""
    if not recent_trades:
        return False
        
    for trade in recent_trades:
        # trade is expected to be a dict-like row
        if (trade["symbol"] == symbol 
            and trade["action"] == "SELL"
            and _days_between(trade["date"], _today()) < cooldown_days):
            return True
    return False

def _build_recommendation(symbol, action, consensus, reasons, position):
    """Build the standardized recommendation dict."""
    signal = consensus["final_signal"]
    risk = consensus["risk_assessment"]
    bull = consensus["bull_case"]
    bear = consensus["bear_case"]
    agree = consensus["agent_agreement"]
    
    return {
        "symbol": symbol,
        "action": action,
        "signal": signal["prediction"],
        "confidence": signal["confidence"],
        "raw_confidence": signal.get("raw_confidence", signal["confidence"]),
        "calibrated_confidence": signal.get("calibrated_confidence", signal["confidence"]),
        "expected_edge_pct": signal.get("expected_edge_pct"),
        "ranking_score": signal.get("ranking_score"),
        "momentum_alignment": consensus.get("momentum_alignment"),
        "conviction": signal["conviction"],
        "risk_action": risk["action"],
        "reasons": reasons,
        "reasons_ar": translate_reasons(reasons),
        "metadata": {
            "bull_score": bull["bull_score"],
            "bear_score": bear["bear_score"],
            "agents_agreeing": agree["agreeing"],
            "agents_total": agree["total"],
            "risk_flags": risk.get("risk_flags", [])
        }
    }

def generate_recommendation(
    symbol: str,
    consensus: dict,           # From run_consensus() output
    current_position: dict,    # None if no open position, else position row
    recent_trades: list,       # Last N trade recommendations for this user+symbol
    open_position_count: int,  # How many open positions user currently has
    max_positions: int         # User's tier limit
) -> dict:
    
    signal = consensus["final_signal"]["prediction"]     # UP / DOWN / FLAT
    confidence = consensus["final_signal"]["confidence"]  # 0-100
    conviction = consensus["final_signal"]["conviction"]  # HIGH / MEDIUM / LOW
    risk_action = consensus["risk_assessment"]["action"]  # PASS / FLAG / DOWNGRADE / BLOCK
    bull_score = consensus["bull_case"]["bull_score"]
    bear_score = consensus["bear_case"]["bear_score"]
    
    reasons = []
    has_position = current_position is not None
    
    # ─── CASE 1: USER HAS AN OPEN POSITION ───────────────────
    if has_position:
        
        # SELL triggers (check in priority order)
        
        # 1. Signal reversed to DOWN
        if signal == "DOWN" and TRADE_CONFIG["sell_on_reversal"]:
            reasons.append(f"Signal reversed to DOWN — closing position")
            reasons.append(f"Bear score ({bear_score}) now dominates")
            return _build_recommendation(symbol, "SELL", consensus, reasons, current_position)
        
        # 2. Risk_Agent DOWNGRADED or BLOCKED
        if risk_action in ("DOWNGRADE", "BLOCK") and TRADE_CONFIG["sell_on_downgrade"]:
            flags = consensus["risk_assessment"].get("risk_flags", [])
            flag_summary = flags[0]["detail"] if flags else "Multiple risk factors"
            reasons.append(f"Risk_Agent {risk_action} — {flag_summary}")
            reasons.append(f"Position at risk — recommending exit")
            return _build_recommendation(symbol, "SELL", consensus, reasons, current_position)
        
        # 3. Confidence dropped critically
        if confidence < TRADE_CONFIG["sell_on_low_confidence"]:
            reasons.append(f"Confidence dropped to {confidence}% (threshold: {TRADE_CONFIG['sell_on_low_confidence']}%)")
            reasons.append(f"Signal too weak to maintain position")
            return _build_recommendation(symbol, "SELL", consensus, reasons, current_position)
        
        # 4. Bear case overwhelms
        if bear_score >= TRADE_CONFIG["sell_on_bear_dominance"]:
            reasons.append(f"Bear score ({bear_score}) exceeds {TRADE_CONFIG['sell_on_bear_dominance']} threshold")
            reasons.append(f"Risk/reward no longer favorable")
            return _build_recommendation(symbol, "SELL", consensus, reasons, current_position)
        
        # 5. Conviction dropped to LOW with FLAT signal
        if signal == "FLAT" and conviction == TRADE_CONFIG["sell_on_conviction_drop"]:
            reasons.append(f"Signal FLAT with LOW conviction — momentum exhausted")
            return _build_recommendation(symbol, "SELL", consensus, reasons, current_position)
        
        # OTHERWISE: HOLD
        entry_date_str = current_position["entry_date"]
        # Ensure entry_date is a string for today's logic, might come as date obj from DB
        if not isinstance(entry_date_str, str):
            entry_date_str = entry_date_str.strftime("%Y-%m-%d")
            
        days_held = _days_between(entry_date_str, _today())
        reasons.append(f"Position still supported — {signal} signal with {confidence}% confidence")
        reasons.append(f"Holding since {entry_date_str} ({days_held} days)")
        if bull_score > bear_score:
            reasons.append(f"Bull ({bull_score}) still > Bear ({bear_score})")
            
        return _build_recommendation(symbol, "HOLD", consensus, reasons, current_position)
    
    # ─── CASE 2: NO OPEN POSITION ────────────────────────────
    else:
        # Check BUY conditions
        buy_eligible = True
        buy_blockers = []
        
        # Must be UP signal (no short selling in v1)
        if signal != "UP":
            buy_eligible = False
            buy_blockers.append(f"Signal is {signal}, not UP")
        
        # Minimum confidence
        if confidence < TRADE_CONFIG["buy_min_confidence"]:
            buy_eligible = False
            buy_blockers.append(f"Confidence {confidence}% below {TRADE_CONFIG['buy_min_confidence']}% minimum")
        
        # Minimum conviction
        min_conv = TRADE_CONFIG["buy_min_conviction"]
        if CONVICTION_ORDER.get(conviction, 0) < CONVICTION_ORDER.get(min_conv, 0):
            buy_eligible = False
            buy_blockers.append(f"Conviction {conviction} below {min_conv} minimum")
        
        # Risk_Agent must not have downgraded
        if risk_action not in TRADE_CONFIG["buy_allowed_risk_actions"]:
            buy_eligible = False
            buy_blockers.append(f"Risk_Agent {risk_action} — not safe to enter")
        
        # Bull score threshold
        if bull_score < TRADE_CONFIG["buy_min_bull_score"]:
            buy_eligible = False
            buy_blockers.append(f"Bull score {bull_score} below {TRADE_CONFIG['buy_min_bull_score']} minimum")
        
        # Bear score cap
        if bear_score > TRADE_CONFIG["buy_max_bear_score"]:
            buy_eligible = False
            buy_blockers.append(f"Bear score {bear_score} exceeds {TRADE_CONFIG['buy_max_bear_score']} maximum")
        
        # Position limit
        if open_position_count >= max_positions:
            buy_eligible = False
            buy_blockers.append(f"Already at max {max_positions} open positions")
        
        # Cooldown check
        if _in_cooldown(symbol, recent_trades, TRADE_CONFIG["cooldown_days"]):
            buy_eligible = False
            buy_blockers.append(f"Stock in {TRADE_CONFIG['cooldown_days']}-day cooldown after recent SELL")
        
        if buy_eligible:
            reasons.append(f"{consensus['agent_agreement']['agreeing']}/{consensus['agent_agreement']['total']} agents signal UP")
            reasons.append(f"Confidence {confidence}% with {conviction} conviction")
            reasons.append(f"Bull ({bull_score}) vs Bear ({bear_score}) — favorable")
            reasons.append(f"Risk_Agent: {risk_action}")
            reasons.append(f"No existing position — Opening new long position")
            return _build_recommendation(symbol, "BUY", consensus, reasons, None)
        else:
            # WATCH — not strong enough or blocked
            reasons.append(f"Signal: {signal} ({confidence}%, {conviction})")
            for blocker in buy_blockers[:3]:  # Top 3 reasons
                reasons.append(blocker)
            return _build_recommendation(symbol, "WATCH", consensus, reasons, None)

def score_recommendation_priority(rec: dict) -> float:
    """Score recommendations for ranking."""
    action_weights = {"BUY": 100, "SELL": 90, "HOLD": 30, "WATCH": 10}
    conviction_weights = {"HIGH": 30, "MEDIUM": 15, "LOW": 5}
    
    base = action_weights.get(rec["action"], 0)
    conviction_bonus = conviction_weights.get(rec.get("conviction", "LOW"), 0)
    confidence_bonus = rec.get("confidence", 0) * 0.3  # 0-30 points
    
    # Boost urgency: SELL on reversal is more urgent than SELL on low confidence
    if rec["action"] == "SELL" and rec.get("signal") == "DOWN":
        base += 20  # Signal reversal = urgent
    
    return base + conviction_bonus + confidence_bonus

def calculate_risk_levels(symbol: str, consensus: dict, market_data: dict) -> dict:
    """Calculate suggested stop-loss and target."""
    close = market_data.get("close", 0)
    if close <= 0:
        return {
            "stop_loss_pct": 0, "target_pct": 0,
            "stop_loss_price": 0, "target_price": 0, "risk_reward_ratio": 0
        }

    atr = market_data.get("atr", close * 0.03)  # Default 3% if no ATR
    conviction = consensus["final_signal"]["conviction"]
    
    # Stop loss: 1.5x ATR for HIGH conviction, 1x ATR for MEDIUM, tight for LOW
    atr_multiplier = {"HIGH": 1.5, "MEDIUM": 1.2, "LOW": 1.0}
    stop_distance = atr * atr_multiplier.get(conviction, 1.0)
    stop_loss_pct = round((stop_distance / close) * 100, 1)
    
    # Cap stop loss at reasonable bounds (2-10%)
    stop_loss_pct = max(2.0, min(stop_loss_pct, 10.0))
    
    # Target: 2x stop loss for HIGH, 1.5x for MEDIUM, 1.2x for LOW
    target_multiplier = {"HIGH": 2.0, "MEDIUM": 1.5, "LOW": 1.2}
    target_pct = round(stop_loss_pct * target_multiplier.get(conviction, 1.5), 1)
    
    # Cap target at 52-week high distance if available
    high_52w = market_data.get("high_52w")
    if high_52w and high_52w > close:
        max_upside = round(((high_52w - close) / close) * 100, 1)
        # If max upside is very small, we depend on conviction, but let's clamp target if upside is huge
        # Actually logic says: target_pct = min(target_pct, max(max_upside, 5.0))
        target_pct = min(target_pct, max(max_upside, 5.0))
    
    return {
        "stop_loss_pct": stop_loss_pct,
        "target_pct": target_pct,
        "stop_loss_price": round(close * (1 - stop_loss_pct / 100), 2),
        "target_price": round(close * (1 + target_pct / 100), 2),
        "risk_reward_ratio": round(target_pct / stop_loss_pct, 2) if stop_loss_pct > 0 else 0
    }
