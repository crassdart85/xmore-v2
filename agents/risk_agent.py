"""
Risk Agent — Layer 3 Gatekeeper

Evaluates consensus signals against configurable risk parameters:
  - Stock-level: liquidity, volatility, bid-ask spread
  - Portfolio-level: sector concentration, maximum drawdown
  
Returns one of four actions:
  PASS      — Signal is safe, no adjustment
  FLAG      — Signal carries caveats, show warning
  DOWNGRADE — Lower conviction (e.g. Strong -> Moderate)
  BLOCK     — Drop the signal entirely
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ============================================
# DEFAULT RISK CONFIGURATION
# ============================================
# These can be overridden via config.py RISK_CONFIG or env vars

DEFAULT_RISK_CONFIG = {
    # Stock-level risk
    "min_avg_volume_20d": 50000,       # Minimum 20-day avg volume for liquidity
    "max_bid_ask_spread_pct": 3.0,     # Max bid-ask spread as % of price
    "max_volatility_20d": 0.06,        # Max 20-day daily volatility (std of returns)
    "min_price": 1.0,                  # Minimum stock price (EGP)
    
    # Portfolio-level risk
    "max_sector_concentration": 0.40,   # Max 40% of signals in one sector
    "max_correlated_signals": 3,       # Max same-direction signals in correlated group
    
    # Signal quality risk
    "min_bull_bear_gap": 10,           # Min gap between bull and bear scores
    "min_agent_agreement": 0.5,        # At least 50% of agents must agree
    "max_bear_score": 75,              # If bear score exceeds this, block
    
    # Drawdown risk
    "max_5d_drawdown_pct": -0.15,      # Block if stock dropped >15% in 5 days
    "max_20d_drawdown_pct": -0.25,     # Block if stock dropped >25% in 20 days
}


# Sector mapping for concentration checks
SECTOR_MAP = {
    # Banking & Financial
    "COMI.CA": "banking", "HRHO.CA": "financial", "EMFD.CA": "financial",
    # Real Estate
    "TMGH.CA": "real_estate", "PHDC.CA": "real_estate", "MNHD.CA": "real_estate",
    "OCDI.CA": "real_estate",
    # Industrial / Utilities
    "ORAS.CA": "industrial", "SWDY.CA": "industrial", "ESRS.CA": "industrial",
    # Consumer / Telecom
    "EAST.CA": "consumer", "ETEL.CA": "telecom", "FWRY.CA": "fintech",
    "JUFO.CA": "consumer", "ORWE.CA": "consumer",
    # Healthcare
    "CCAP.CA": "healthcare",
    # Chemicals / Energy
    "ABUK.CA": "chemicals", "MFPC.CA": "chemicals", "SKPC.CA": "chemicals",
    "AMOC.CA": "energy", "ALCN.CA": "logistics",
    "EFIH.CA": "industrial",
    # US Tech
    "AAPL": "tech", "GOOGL": "tech", "MSFT": "tech", "AMZN": "tech",
    "META": "tech", "TSLA": "auto_tech", "NVDA": "tech",
    # US Finance
    "JPM": "banking", "V": "financial", "BAC": "banking",
    # US Other
    "JNJ": "healthcare", "WMT": "consumer", "XOM": "energy",
    "PG": "consumer", "HD": "consumer",
}


def evaluate_risk(symbol: str,
                  consensus_result: Dict[str, Any],
                  market_data: Optional[Dict[str, Any]] = None,
                  portfolio_signals: Optional[List[Dict[str, Any]]] = None,
                  risk_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Gate a consensus signal through risk checks.
    
    Args:
        symbol: Stock ticker
        consensus_result: Dict with keys: final_signal, bull_score, bear_score,
                         agent_agreement, conviction, confidence
        market_data: Dict with volume_20d_avg, volatility_20d, price, drawdown_5d, drawdown_20d
        portfolio_signals: List of (symbol, signal) already decided this run —
                          used for sector concentration check
        risk_config: Override risk thresholds (uses DEFAULT_RISK_CONFIG if None)
    
    Returns:
        {
            "action": "PASS" | "FLAG" | "DOWNGRADE" | "BLOCK",
            "original_signal": ...,
            "adjusted_signal": ...,          # May differ if downgraded
            "original_conviction": ...,
            "adjusted_conviction": ...,
            "risk_flags": [...],             # Human-readable risk warnings
            "risk_flags_ar": [...],          # Arabic versions
            "risk_score": 0-100,             # Overall risk score
            "details": { ... }               # Detailed risk data
        }
    """
    cfg = {**DEFAULT_RISK_CONFIG, **(risk_config or {})}
    
    signal = consensus_result.get('final_signal', 'HOLD')
    conviction = consensus_result.get('conviction', 'LOW')
    bull_score = consensus_result.get('bull_score', 0)
    bear_score = consensus_result.get('bear_score', 0)
    agreement = consensus_result.get('agent_agreement', 0)
    confidence = consensus_result.get('confidence', 50)
    
    flags = []
    flags_ar = []
    risk_score = 0
    details = {}
    
    # === CHECK 1: LIQUIDITY ===
    if market_data and market_data.get('volume_20d_avg') is not None:
        avg_vol = market_data['volume_20d_avg']
        if avg_vol < cfg['min_avg_volume_20d']:
            risk_score += 20
            flags.append(f"⚠️ Low liquidity: {avg_vol:,.0f} avg vol (min: {cfg['min_avg_volume_20d']:,.0f})")
            flags_ar.append(f"⚠️ سيولة منخفضة: متوسط الحجم {avg_vol:,.0f} (الحد الأدنى: {cfg['min_avg_volume_20d']:,.0f})")
            details['liquidity_risk'] = True
    
    # === CHECK 2: VOLATILITY ===
    # Prefer GARCH one-step-ahead conditional vol (forward-looking) over historical 20d std.
    # GARCH sigma_t captures current volatility clustering; historical vol can lag market moves.
    if market_data:
        garch_vol = market_data.get('garch_forecast_vol')
        hist_vol  = market_data.get('volatility_20d')
        vol = garch_vol if garch_vol is not None else hist_vol
        if vol is not None and vol > cfg['max_volatility_20d']:
            risk_score += 15
            vol_source = "GARCH" if garch_vol is not None else "20d hist"
            flags.append(f"⚠️ High volatility ({vol_source}): {vol:.1%} daily (max: {cfg['max_volatility_20d']:.1%})")
            flags_ar.append(f"⚠️ تقلب عالي ({vol_source}): {vol:.1%} يومي (الحد الأقصى: {cfg['max_volatility_20d']:.1%})")
            details['volatility_risk'] = True
            details['vol_source'] = vol_source
    
    # === CHECK 3: DRAWDOWN ===
    if market_data:
        drawdown_5d = market_data.get('drawdown_5d', 0)
        drawdown_20d = market_data.get('drawdown_20d', 0)
        
        if drawdown_5d < cfg['max_5d_drawdown_pct']:
            risk_score += 25
            flags.append(f"🚨 Severe 5-day drawdown: {drawdown_5d:.1%}")
            flags_ar.append(f"🚨 تراجع حاد في 5 أيام: {drawdown_5d:.1%}")
            details['severe_drawdown'] = True
        
        if drawdown_20d < cfg['max_20d_drawdown_pct']:
            risk_score += 20
            flags.append(f"🚨 Severe 20-day drawdown: {drawdown_20d:.1%}")
            flags_ar.append(f"🚨 تراجع حاد في 20 يوم: {drawdown_20d:.1%}")
            details['severe_drawdown_20d'] = True
    
    # === CHECK 4: SIGNAL QUALITY ===
    bull_bear_gap = bull_score - bear_score
    if bear_score > cfg['max_bear_score']:
        risk_score += 25
        flags.append(f"🚨 Very high bear score: {bear_score}/100 — strong case AGAINST the signal")
        flags_ar.append(f"🚨 مؤشر الدب مرتفع جداً: {bear_score}/100 — حالة قوية ضد الإشارة")
        details['bear_override'] = True
    
    if bull_bear_gap < cfg['min_bull_bear_gap']:
        risk_score += 10
        flags.append(f"⚠️ Narrow bull-bear gap: {bull_bear_gap}pts — contested signal")
        flags_ar.append(f"⚠️ فارق ضيق بين الثور والدب: {bull_bear_gap} نقطة — إشارة متنازع عليها")
        details['contested_signal'] = True
    
    if agreement < cfg['min_agent_agreement']:
        risk_score += 10
        flags.append(f"⚠️ Low agent agreement: {agreement:.0%}")
        flags_ar.append(f"⚠️ اتفاق منخفض بين الوكلاء: {agreement:.0%}")
        details['low_agreement'] = True
    
    # === CHECK 5: SECTOR CONCENTRATION ===
    if portfolio_signals:
        sector = SECTOR_MAP.get(symbol, 'unknown')
        same_sector_signals = [
            ps for ps in portfolio_signals
            if SECTOR_MAP.get(ps.get('symbol', ''), 'unknown') == sector
            and ps.get('signal', 'HOLD') != 'HOLD'
        ]
        total_non_hold = [ps for ps in portfolio_signals if ps.get('signal', 'HOLD') != 'HOLD']
        
        if total_non_hold:
            sector_pct = len(same_sector_signals) / len(total_non_hold)
            if sector_pct > cfg['max_sector_concentration']:
                risk_score += 10
                flags.append(f"⚠️ Sector concentration: {sector_pct:.0%} of signals in '{sector}'")
                flags_ar.append(f"⚠️ تركز قطاعي: {sector_pct:.0%} من الإشارات في '{sector}'")
                details['sector_concentration'] = True
    
    # === CHECK 6: PENNY STOCK ===
    if market_data and market_data.get('price') is not None:
        if market_data['price'] < cfg['min_price']:
            risk_score += 10
            flags.append(f"⚠️ Penny stock: price {market_data['price']:.2f} EGP")
            flags_ar.append(f"⚠️ سهم رخيص: السعر {market_data['price']:.2f} جنيه")
            details['penny_stock'] = True
    
    risk_score = min(100, risk_score)
    
    # === DETERMINE ACTION ===
    action = "PASS"
    adjusted_signal = signal
    adjusted_conviction = conviction
    
    conviction_levels = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    
    if risk_score >= 60 or details.get('severe_drawdown') or details.get('bear_override'):
        action = "BLOCK"
        adjusted_signal = "HOLD"
        adjusted_conviction = "BLOCKED"
    elif risk_score >= 40:
        action = "DOWNGRADE"
        # Lower conviction by 1 level
        current_idx = conviction_levels.index(conviction) if conviction in conviction_levels else 1
        adjusted_idx = max(0, current_idx - 1)
        adjusted_conviction = conviction_levels[adjusted_idx]
    elif risk_score >= 15:
        action = "FLAG"
        # Keep signal but flag it
    else:
        action = "PASS"
    
    logger.info(f"[{symbol}] Risk: score={risk_score}, action={action}, flags={len(flags)}")
    
    return {
        "action": action,
        "original_signal": signal,
        "adjusted_signal": adjusted_signal,
        "original_conviction": conviction,
        "adjusted_conviction": adjusted_conviction,
        "risk_flags": flags,
        "risk_flags_ar": flags_ar,
        "risk_score": risk_score,
        "details": details
    }
