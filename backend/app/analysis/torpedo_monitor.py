"""
torpedo_monitor — Prüft ob neue News bestehende Report-Empfehlungen infrage stellen

Input:  Material-News aus dem Kurzzeit-Gedächtnis
Output: Telegram-Alert wenn Empfehlung gefährdet
Deps:   memory/short_term.py, memory/watchlist.py, alerts/telegram.py
Config: Keine
API:    Keine
"""

from backend.app.memory.short_term import get_material_news
from backend.app.memory.watchlist import get_watchlist
from backend.app.alerts.telegram import send_telegram_alert
from backend.app.logger import get_logger

logger = get_logger(__name__)


async def check_torpedo_updates():
    """
    Prüft für alle Watchlist-Ticker ob seit dem letzten Scan
    neue Torpedo-Events aufgetaucht sind.
    Wird am Ende jedes News-Pipeline-Laufs aufgerufen.
    """
    wl = await get_watchlist()

    for item in wl:
        ticker = item["ticker"]
        material_news = await get_material_news(ticker)

        if material_news:
            logger.info(f"Torpedo-Monitor: {len(material_news)} Material-Events für {ticker}")
            
            # Simple alerting mechanism for now.
            # We can extend this to load the last Audit Report and have DeepSeek evaluate the impact.
            # But for Phase 3B keeping it simple to just log/alert that a Torpedo event happened recently.
            # Note: The sec_edgar.py and news_processor.py already send direct alerts, so this acts as a 
            # secondary monitor to correlate torpedo events with recent reports.
