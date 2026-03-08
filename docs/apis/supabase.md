# Supabase

Dashboard: https://supabase.com/dashboard
Docs: https://supabase.com/docs
Python-Client: `supabase-py` (bereits in requirements.txt)

## Konfiguration
- SUPABASE_URL: Projekt-URL (z.B. https://xxxx.supabase.co)
- SUPABASE_KEY: anon/public Key oder service_role Key
- SUPABASE_PASSWORD: `Glurak.1944!` (Projekt-Passwort)

## Python-Client Nutzung

```python
from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# SELECT
result = client.table("watchlist").select("*").execute()
rows = result.data

# SELECT mit Filter
result = client.table("watchlist").select("*").eq("ticker", "AAPL").execute()

# INSERT
result = client.table("watchlist").insert({
    "ticker": "NVDA",
    "company_name": "NVIDIA",
    "sector": "Technology"
}).execute()

# UPDATE
result = client.table("watchlist").update({
    "notes": "Neuer Kommentar"
}).eq("ticker", "NVDA").execute()

# DELETE
result = client.table("watchlist").delete().eq("ticker", "NVDA").execute()

# UPSERT (Insert oder Update)
result = client.table("long_term_memory").upsert({
    "ticker": "AAPL",
    "quarter": "Q1_2026",
    "eps_actual": 1.65
}).execute()
```

## Tabellen (siehe database/schema.sql)
- watchlist
- short_term_memory
- long_term_memory
- macro_snapshots
- btc_snapshots
- audit_reports

## Tipps
- Free Tier: 500MB DB, 50.000 Reads/Monat
- Row-Level Security (RLS) aktivieren wenn das Dashboard public wird
- JSONB-Felder für flexible Daten (z.B. bullet_points in short_term_memory)
- Supabase generiert automatisch UUIDs als Primary Keys
