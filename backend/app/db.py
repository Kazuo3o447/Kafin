"""
db.py — Datenbankverbindung

HINWEIS: get_supabase_client() ist ein Compatibility-Shim.
Es gibt KEIN echtes Supabase mehr — alles läuft auf
lokalem PostgreSQL 16 (Docker-Container kafin-postgres).

Migration abgeschlossen in Kaskade 6 (v6.0.4).

Leitet get_supabase_client() an den neuen
PostgreSQL-Adapter weiter.
Alle bestehenden Importe bleiben funktionsfähig.
"""
from backend.app.database import (
    get_supabase_client,
    get_db_client,
    get_pool,
)

__all__ = [
    "get_supabase_client",
    "get_db_client",
    "get_pool",
]
