"""
macro_processor — Verarbeitung von globalen Wirtschaftsdaten (GENERAL_MACRO)
"""
import asyncio
from datetime import datetime
from typing import List
import json

from backend.app.logger import get_logger
from backend.app.data.finnhub import get_economic_calendar
from backend.app.analysis.deepseek import call_deepseek
from backend.app.memory.short_term import save_bullet_points, get_existing_urls

logger = get_logger(__name__)

async def fetch_global_macro_events() -> dict:
    """
    Ruft den Wirtschaftskalender ab, fasst Top-Events mit DeepSeek zusammen
    und speichert sie als Stichpunkte unter GENERAL_MACRO im Kurzzeit-Gedächtnis.
    """
    stats = {"events_fetched": 0, "events_saved": 0}
    
    try:
        events = await get_economic_calendar(days_back=7, days_forward=7)
        stats["events_fetched"] = len(events)
    except Exception as e:
        logger.error(f"Fehler beim Abrufen des Wirtschaftskalenders: {e}")
        return stats
    
    if not events:
        logger.info("Keine Makro-Events gefunden.")
        return stats

    # Deduplizierung: Einmal am Tag zusammenfassen reicht
    existing_urls = await get_existing_urls("GENERAL_MACRO")
    today_str = datetime.now().strftime("%Y-%m-%d")
    macro_id = f"macro_summary_{today_str}"
    
    if macro_id in existing_urls:
        logger.info(f"Makro-Zusammenfassung für heute ({macro_id}) existiert bereits.")
        return stats

    # Events formatieren für DeepSeek
    lines = []
    for ev in events:
        actual = ev.get("actual")
        est = ev.get("estimate")
        unit = ev.get("unit", "")
        if actual is not None and est is not None:
            lines.append(f"{ev.get('date', '?')}: {ev.get('event', '?')} - Actual: {actual}{unit} (Est: {est}{unit})")
        elif est is not None:
            lines.append(f"{ev.get('date', '?')}: {ev.get('event', '?')} - Est: {est}{unit} (ausstehend)")
        else:
            lines.append(f"{ev.get('date', '?')}: {ev.get('event', '?')}")
            
    events_text = "\n".join(lines)
    
    sys_prompt = (
        "Du bist ein Marktanalyst. Fasse die folgenden globalen Wirtschaftsevents "
        "(CPI, NFP, Fed etc.) in 3 bis max. 5 prägnanten deutschen Stichpunkten zusammen. "
        "Fokussiere dich auf die Marktauswirkungen (bullish/bearish). Sei sehr kurz und direkt.\n"
        "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt im Format: {\"bullets\": [\"Stichpunkt 1\", \"Stichpunkt 2\"]}"
    )
    user_prompt = f"Hier sind die High-Impact Events:\n\n{events_text}"

    try:
        result_json_str = await call_deepseek(sys_prompt, user_prompt)
        
        # Versuche JSON Parsing (DeepSeek könnte Markdown-Codeblöcke mitgeben)
        cleaned_json = result_json_str.strip()
        if cleaned_json.startswith("```json"):
            cleaned_json = cleaned_json[7:]
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3]
            
        data = json.loads(cleaned_json)
        bullets = data.get("bullets", [])
        
        if not bullets:
            raise ValueError("Keine Bullets im JSON gefunden.")
            
        await save_bullet_points(
            ticker="GENERAL_MACRO",
            date=datetime.now(),
            source="deepseek_macro",
            bullet_points=bullets,
            sentiment_score=0.0,
            category="macro",
            url=macro_id,
            is_material=True
        )
        stats["events_saved"] += len(bullets)
        logger.info(f"Makro-Zusammenfassung mit {len(bullets)} Stichpunkten gespeichert.")

    except Exception as e:
        logger.error(f"Fehler bei DeepSeek Makro-Analyse oder Speicherung: {e}")
        
    return stats
