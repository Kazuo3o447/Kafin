"""
telegram — Formatierung und Versand an Telegram Bot

Input:  Nachrichten-String (z.B. Torpedo-Warnung)
Output: Boolean (Erfolg)
Deps:   httpx, tenacity, config, logger
Config: telegram_bot_token, telegram_chat_id
API:    Telegram Bot API
"""
import httpx
from typing import List, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
)
async def _send_message_sync(text: str, token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        return True

async def send_telegram_alert(message: str) -> bool:
    """Sendet einen Alert (z.B. Torpedo-Warnung) via Telegram."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    
    if not token or not chat_id:
        logger.warning("Telegram Bot Token oder Chat ID fehlt. Alert wird übersprungen.")
        return False
        
    try:
        success = await _send_message_sync(message, token, chat_id)
        if success:
            logger.info("Telegram Alert erfolgreich gesendet.")
        return success
    except Exception as e:
        logger.error(f"Fehler beim Senden des Telegram Alerts: {e}")
        return False
        
def format_torpedo_alert(ticker: str, score: float, reasons: List[str]) -> str:
    """Formatiert eine Torpedo-Warnung für Telegram."""
    alert_text = f"🚨 <b>TORPEDO-WARNUNG: {ticker}</b> 🚨\n\n"
    alert_text += f"Score: <b>{score:.2f} / 10.0</b>\n\n"
    alert_text += "<b>Kritische Indikatoren:</b>\n"
    for reason in reasons:
        alert_text += f"• {reason}\n"
        
    return alert_text

def format_narrative_shift_alert(ticker: str, shift_type: str, reasoning: str, headline: str, url: str, rss_url: str = "") -> str:
    """Formatiert einen priorisierten Alert für einen fundamentalen Narrative Shift."""
    from html import escape
    
    ticker_safe = escape(ticker)
    shift_type_safe = escape(shift_type)
    headline_safe = escape(headline)
    reasoning_safe = escape(reasoning) if reasoning else ""
    
    if shift_type == "Strategic-Downsizing":
        alert_text = f"🚨 <b>TORPEDO-ALERT: INVESTITIONS-RÜCKBAU</b> 🚨\n"
        alert_text += f"Ticker: <b>{ticker_safe}</b>\n\n"
    else:
        alert_text = f"🌀 <b>NARRATIVE SHIFT ERKANNT</b> 🌀\n"
        alert_text += f"Ticker: <b>{ticker_safe}</b> | Typ: <i>{shift_type_safe}</i>\n\n"
        
    alert_text += f"<b>Headline:</b> {headline_safe}\n"
    if reasoning_safe:
        alert_text += f"<b>KI Analyse:</b> <i>{reasoning_safe}</i>\n"
        
    if url:
        alert_text += f"\n<a href='{url}'>Zur Meldung</a>"
        
    return alert_text


async def send_post_earnings_alert(
    ticker: str,
    company_name: str,
    eps_actual: Optional[float],
    eps_consensus: Optional[float],
    eps_surprise_pct: Optional[float],
    revenue_actual: Optional[float],
    revenue_consensus: Optional[float],
    ah_change_pct: Optional[float],
    expected_move_pct: Optional[float],
    rsi: Optional[float],
    opp_score: Optional[float],
    torpedo_score: Optional[float],
    win_rate: Optional[int],
    recommendation: Optional[str],
) -> None:
    """Reicher Post-Earnings Kontext-Alert."""

    # EPS-Badge
    if eps_surprise_pct is not None:
        if eps_surprise_pct > 5:
            eps_badge = f"✅ Beat +{eps_surprise_pct:.1f}%"
        elif eps_surprise_pct < -5:
            eps_badge = f"❌ Miss {eps_surprise_pct:.1f}%"
        else:
            eps_badge = f"➖ In-Line {eps_surprise_pct:+.1f}%"
    else:
        eps_badge = "— EPS unbekannt"

    # AH-Reaktion
    if ah_change_pct is not None:
        ah_emoji = "📈" if ah_change_pct >= 0 else "📉"
        ah_line = f"{ah_emoji} AH-Reaktion: {ah_change_pct:+.1f}%"
        # Vergleich mit Expected Move
        if expected_move_pct and abs(ah_change_pct) > expected_move_pct:
            ah_line += f" ⚡ (Expected Move ±{expected_move_pct:.1f}% überschritten)"
        elif expected_move_pct:
            ah_line += f" (EM ±{expected_move_pct:.1f}%)"
    else:
        ah_line = "📊 AH-Reaktion: —"

    # Setup-Hinweis
    setup_hint = ""
    if ah_change_pct is not None and eps_surprise_pct is not None:
        if eps_surprise_pct > 5 and ah_change_pct < -2:
            setup_hint = "\n⚡ <b>Mögliche Kaufgelegenheit</b> — Beat aber AH-Dip"
        elif eps_surprise_pct < -5 and ah_change_pct > 2:
            setup_hint = "\n⚠️ <b>Vorsicht</b> — Miss aber AH-Bounce (Erwartungen tief)"

    # Win-Rate
    wr_line = (
        f"📊 Kafin-Trefferquote für {ticker}: {win_rate}%"
        if win_rate is not None
        else ""
    )

    msg = (
        f"🎯 <b>POST-EARNINGS: {ticker}</b> — {company_name}\n\n"
        f"<b>EPS:</b> {eps_badge}\n"
    )
    if eps_actual is not None and eps_consensus is not None:
        msg += (
            f"  Gemeldet: ${eps_actual:.2f} | "
            f"Konsens: ${eps_consensus:.2f}\n"
        )
    if revenue_actual is not None:
        rev_b = revenue_actual / 1e9
        rev_cons = (
            f" | Konsens: ${revenue_consensus/1e9:.1f}B"
            if revenue_consensus else ""
        )
        msg += f"<b>Revenue:</b> ${rev_b:.1f}B{rev_cons}\n"

    msg += f"\n{ah_line}\n"

    if rsi is not None:
        rsi_note = (
            " — überverkauft" if rsi < 35
            else " — überkauft" if rsi > 65
            else ""
        )
        msg += f"RSI: {rsi:.0f}{rsi_note}\n"

    if opp_score is not None:
        msg += (
            f"Opp-Score: {opp_score:.1f} | "
            f"Torpedo: {torpedo_score:.1f}\n"
        )
    if wr_line:
        msg += f"{wr_line}\n"
    if setup_hint:
        msg += setup_hint

    await send_telegram_alert(msg)
