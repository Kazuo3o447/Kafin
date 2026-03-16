"""
init_watchlist — Befüllt Supabase-Watchlist mit Default-Titeln falls leer.

Wird beim Backend-Start einmalig aufgerufen.
"""
from backend.app.db import get_supabase_client
from backend.app.logger import get_logger

logger = get_logger(__name__)

DEFAULT_WATCHLIST = [
    {"ticker": "NVDA", "company_name": "NVIDIA Corp.", "sector": "Technology", "notes": "KI/Datacenter Bellwether", "is_active": True},
    {"ticker": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "notes": "Consumer Tech + Services", "is_active": True},
    {"ticker": "MSFT", "company_name": "Microsoft Corp.", "sector": "Technology", "notes": "Cloud/Azure + KI-CapEx", "is_active": True},
    {"ticker": "META", "company_name": "Meta Platforms", "sector": "Technology", "notes": "KI-CapEx Ausweitung", "is_active": True},
    {"ticker": "GOOGL", "company_name": "Alphabet Inc.", "sector": "Technology", "notes": "Cloud + KI", "is_active": True},
    {"ticker": "AMZN", "company_name": "Amazon.com Inc.", "sector": "Technology", "notes": "AWS + E-Commerce", "is_active": True},
    {"ticker": "TSMC", "company_name": "Taiwan Semiconductor", "sector": "Technology", "notes": "Chip-Fertigung, CapEx-Empfänger", "is_active": True},
    {"ticker": "MU", "company_name": "Micron Technology", "sector": "Technology", "notes": "HBM/DRAM für KI", "is_active": True},
    {"ticker": "CRM", "company_name": "Salesforce Inc.", "sector": "Technology", "notes": "Enterprise SaaS, Agentforce", "is_active": True},
    {"ticker": "MDB", "company_name": "MongoDB Inc.", "sector": "Technology", "notes": "NoSQL/Atlas, KI-RAG Plays — TORPEDO-REFERENZ", "is_active": True},
]


async def ensure_watchlist_populated():
    """Prüft ob Watchlist in Supabase Einträge hat. Wenn leer: Default einfügen."""
    try:
        db = get_supabase_client()
        if db is None:
            logger.warning("Supabase nicht verfügbar. Watchlist-Init übersprungen.")
            return

        result = db.table("watchlist").select("ticker").limit(1).execute()
        if result.data:
            logger.info(f"Watchlist enthält bereits Daten. Init übersprungen.")
            return

        logger.info(f"Watchlist ist leer. Füge {len(DEFAULT_WATCHLIST)} Default-Ticker ein...")
        for item in DEFAULT_WATCHLIST:
            try:
                db.table("watchlist").insert(item).execute()
                logger.info(f"  ✅ {item['ticker']} eingefügt")
            except Exception as e:
                logger.warning(f"  ⚠️ {item['ticker']} fehlgeschlagen: {e}")

        logger.info("Watchlist-Init abgeschlossen.")
    except Exception as e:
        logger.error(f"Watchlist-Init Fehler: {e}")
