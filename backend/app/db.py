"""
db.py — Datenbank-Verbindung

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
