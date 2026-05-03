# Legacy Supabase Compatibility Shim

Diese Datei ist historisch erhalten, aber **Supabase ist nicht mehr das Runtime-Backend**.
Kafin verwendet lokal **PostgreSQL 16** im Docker-Container (`kafin-postgres`).

`backend/app/db.py` stellt `get_supabase_client()` als **Compatibility-Shim** bereit,
damit ältere Codepfade weiter funktionieren.
Die Rückgabe ist ein lokaler PostgreSQL-Client aus `backend/app/database.py`.

## Was du heute verwenden sollst

```python
from backend.app.db import get_supabase_client

db = get_supabase_client()
rows = await db.table("watchlist").select("*").execute_async()
```

## Wichtige Hinweise

- **Keine Cloud-Verbindung**: Es gibt keinen produktiven Supabase-Account mehr für die App.
- **Keine Secrets in Doku**: Alte URL-/Key-Werte wurden absichtlich entfernt.
- **CRUD bleibt kompatibel**: Bestehende Tabellen wie `watchlist`, `short_term_memory`, `long_term_memory`, `macro_snapshots`, `btc_snapshots` und `audit_reports` laufen über den lokalen DB-Adapter.
- **Neuer Code**: Für neue Pfade bitte direkt `get_db_client()` / `get_pool()` verwenden, wenn kein Supabase-Kompatibilitätslayer nötig ist.

## Hintergrund

Früher wurde `supabase-py` direkt verwendet. Heute ist die Doku nur noch als Übergangshilfe für Legacy-Code gedacht.
Alle tatsächlichen Laufzeitzugriffe gehen gegen die lokale Container-PostgreSQL-Datenbank.
