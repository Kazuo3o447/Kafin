# memory Modul

Handles Supabase CRUD Operationen.

> [!NOTE]
> Die echte Supabase-Anbindung für die Watchlist ist aktuell noch in Arbeit (Platzhalter in `watchlist.py`). 
> Derzeit werden In-Memory Mock-Daten verwendet, wenn `use_mock_data: true` gesetzt ist.

**Dateien:**
- `short_term.py`: News und schnelle Stichpunkte
- `long_term.py`: Historische Earnings-Überprüfungen
- `watchlist.py`: Aktien auf dem Radar, Speicherung temporärer Mock-Daten. Bietet Abfragen für diese Woche.
- `macro.py`: Historische Makro-Regime-Snapshots
- `btc.py`: Historische Krypto-Snapshots
