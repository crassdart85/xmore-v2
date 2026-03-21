"""
KSA WhatsApp Channel Publisher — broadcasts daily KSA signals via WHAPI.cloud.
Uses KSA_WHAPI_TOKEN and KSA_WHATSAPP_CHANNEL_ID env vars.
"""
import os
import json
import logging
import requests
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

WHAPI_BASE = "https://gate.whapi.cloud"
KSA_TZ = pytz.timezone("Asia/Riyadh")

SIGNAL_EMOJI = {"UP": "🟢", "DOWN": "🔴", "HOLD": "⚪"}
CONVICTION_EMOJI = {"VERY_HIGH": "🔥🔥", "HIGH": "🔥", "MODERATE": "✅", "LOW": "⚠️"}


def _build_signal_card(signal: dict) -> str:
    """Format one signal as a WhatsApp message block in Arabic/English."""
    ticker   = signal.get("ticker", "")
    name_ar  = signal.get("name_ar", "")
    direction = signal.get("signal", "HOLD")
    conviction = signal.get("conviction", "MODERATE")
    price    = signal.get("price", 0)
    target   = signal.get("target", 0)
    stop     = signal.get("stop", 0)
    score    = signal.get("xmore_score", 0)
    shariah  = signal.get("shariah_compliant", None)

    shariah_badge = "☪️ شريعة" if shariah else ("" if shariah is None else "")
    sig_emoji     = SIGNAL_EMOJI.get(direction, "⚪")
    conv_emoji    = CONVICTION_EMOJI.get(conviction, "✅")
    price_str     = f"{price:,.2f} ر.س"
    target_str    = f"{target:,.2f} ر.س" if target else "—"
    stop_str      = f"{stop:,.2f} ر.س" if stop else "—"

    lines = [
        f"{sig_emoji} *{ticker}* — {name_ar} {shariah_badge}",
        f"الإشارة: *{direction}* {conv_emoji} | النقاط: {score:.0f}",
        f"السعر: {price_str} | الهدف: {target_str} | الوقف: {stop_str}",
        f"⚠️ وقف الخسارة على مستوى الوسيط فقط، ليس تداول.",
    ]
    return "\n".join(lines)


def _send_whapi(token: str, channel_id: str, text: str) -> bool:
    """Send a text message to a WHAPI channel."""
    url = f"{WHAPI_BASE}/messages/text"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"to": channel_id, "body": text}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        logger.info(f"[KSA] WhatsApp message sent (status {r.status_code})")
        return True
    except Exception as e:
        logger.warning(f"[KSA] WhatsApp send failed: {e}")
        return False


def publish_ksa_daily(signals: list = None):
    """
    Publish today's KSA signals to WhatsApp channel.
    signals: list of signal dicts. If None, fetches from DB.
    Non-fatal — any error is logged and swallowed.
    """
    token      = os.environ.get("KSA_WHAPI_TOKEN", "")
    channel_id = os.environ.get("KSA_WHATSAPP_CHANNEL_ID", "")

    if not token or not channel_id:
        logger.warning("[KSA] KSA_WHAPI_TOKEN or KSA_WHATSAPP_CHANNEL_ID not set — skipping WhatsApp")
        return

    try:
        if signals is None:
            signals = _fetch_todays_signals()

        if not signals:
            logger.info("[KSA] No KSA signals today — skipping WhatsApp publish")
            return

        now_ksa  = datetime.now(KSA_TZ)
        date_str = now_ksa.strftime("%A %d %b %Y")
        header   = (
            f"📊 *Xmore KSA — إشارات تداول اليوم*\n"
            f"📅 {date_str}\n"
            f"{'─' * 30}"
        )
        _send_whapi(token, channel_id, header)

        for sig in signals[:10]:  # Cap at 10 signals per broadcast
            card = _build_signal_card(sig)
            _send_whapi(token, channel_id, card)

        from config.execution_config import TADAWUL_CONFIG
        disclaimer = TADAWUL_CONFIG["disclaimer_ar"]
        footer = f"\n⚠️ *تنبيه قانوني:*\n{disclaimer}\n\n🤖 Powered by Xmore KSA"
        _send_whapi(token, channel_id, footer)

        logger.info(f"[KSA] Published {len(signals)} signals to WhatsApp")

    except Exception as e:
        logger.warning(f"[KSA] WhatsApp publisher error (non-fatal): {e}")


def _fetch_todays_signals() -> list:
    """Fetch today's evaluated KSA signals from DB."""
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur  = conn.cursor()
    cur.execute("""
        SELECT symbol, final_signal, conviction, xmore_score,
               drivers_json, risk_level, expected_move
        FROM consensus_results
        WHERE market_id = 'KSA'
          AND DATE(timestamp) = CURRENT_DATE
          AND final_signal IN ('UP', 'DOWN')
        ORDER BY xmore_score DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "ticker":     r[0],
            "signal":     r[1],
            "conviction": r[2],
            "xmore_score": float(r[3] or 0),
        }
        for r in rows
    ]
