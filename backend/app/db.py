"""
db — Datenbank-Verbindung (Supabase)

Input:  Tabellen-Namen und Queries
Output: Supabase-Antworten (Dicts / Listen)
Deps:   supabase, config, logger
Config: supabase_url, supabase_key aus settings
API:    Supabase REST API
"""
from supabase import create_client, Client
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

def get_supabase_client() -> Client:
    """Holt oder initialisiert den Supabase-Client."""
    url: str = settings.supabase_url
    key: str = settings.supabase_key
    
    if not url or not key:
        logger.warning("Supabase URL oder Key fehlt! Mock-Daten erwartet oder DB-Call wird fehlschlagen.")
        # Wir geben trotzdem ein Mock-ähnliches oder partielles Objekt zurück, wenn nötig 
        # oder wirft in echt einen Error
        
    return create_client(url, key)

# Singleton-Instanz (wird beim Import geladen)
# if settings.supabase_url and settings.supabase_key:
#     supabase = create_client(settings.supabase_url, settings.supabase_key)
# else:
#     supabase = None
