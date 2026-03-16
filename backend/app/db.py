"""
db — Datenbank-Verbindung (Supabase)

Input:  Tabellen-Namen und Queries
Output: Supabase-Antworten (Dicts / Listen)
Deps:   supabase, config, logger
Config: supabase_url, supabase_key aus settings
API:    Supabase REST API
"""
import urllib.parse
from supabase import create_client, Client
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

def _validate_supabase_url(url: str) -> tuple[bool, str]:
    """Validiert die Supabase URL und gibt (is_valid, error_message) zurück."""
    if not url:
        return False, "SUPABASE_URL ist leer oder nicht gesetzt"
    
    if "your-project" in url.lower() or "placeholder" in url.lower():
        return False, f"SUPABASE_URL enthält Platzhalter: {url}"
    
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, f"SUPABASE_URL hat ungültiges Format (fehlendes https:// oder Domain): {url}"
        
        if not parsed.netloc.endswith(".supabase.co"):
            logger.warning(f"SUPABASE_URL endet nicht auf .supabase.co: {parsed.netloc}")
            
    except Exception as e:
        return False, f"SUPABASE_URL Parsing-Fehler: {e}"
    
    return True, ""

def get_supabase_client() -> Client | None:
    """Holt oder initialisiert den Supabase-Client."""
    url: str = settings.supabase_url
    key: str = settings.supabase_key
    
    # Validierung
    is_valid, error_msg = _validate_supabase_url(url)
    if not is_valid:
        logger.error(f"Supabase Konfigurationsfehler: {error_msg}")
        return None
    
    if not url or not key:
        logger.warning("Supabase URL oder Key fehlt! Rueckgabe None.")
        return None
        
    try:
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Supabase Client konnte nicht erstellt werden: {e}")
        return None

# Singleton-Instanz (wird beim Import geladen)
# if settings.supabase_url and settings.supabase_key:
#     supabase = create_client(settings.supabase_url, settings.supabase_key)
# else:
#     supabase = None
