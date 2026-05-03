# data Modul

Beinhaltet Daten-Abruf-Logik pro API.

**Regeln:**
- Jede Datei kapselt genau EINE API (z.B. `finnhub.py`, `fmp.py`).
- Nutze `httpx` für alle Calls.
- Respektiere Mock-Data Toggle aus den Settings (liefere dann via `json.loads` statische JSONs aus `fixtures/` zurück).
