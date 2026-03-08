"""
telegram — Formatierung und Versand an Telegram Bot

Input:  Nachrichten-String (z.B. Torpedo-Warnung)
Output: Boolean (Erfolg)
Deps:   httpx, tenacity, config, logger
Config: telegram_bot_token, telegram_chat_id
API:    Telegram Bot API
"""
import httpx
from typing import List
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
        "parse_mode": "HTML"
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

def format_narrative_shift_alert(ticker: str, shift_type: str, reasoning: str, headline: str, url: str) -> str:
    """Formatiert einen priorisierten Alert für einen fundamentalen Narrative Shift."""
    if shift_type == "Strategic-Downsizing":
        alert_text = f"🚨 <b>TORPEDO-ALERT: INVESTITIONS-RÜCKBAU</b> 🚨\n"
        alert_text += f"Ticker: <b>{ticker}</b>\n\n"
    else:
        alert_text = f"🌀 <b>NARRATIVE SHIFT ERKANNT</b> 🌀\n"
        alert_text += f"Ticker: <b>{ticker}</b> | Typ: <i>{shift_type}</i>\n\n"
        
    alert_text += f"<b>Headline:</b> {headline}\n"
    if reasoning:
        alert_text += f"<b>KI Analyse:</b> <i>{reasoning}</i>\n"
        
    if url:
        alert_text += f"\n<a href='{url}'>Zur Meldung</a>"
        
    return alert_text
