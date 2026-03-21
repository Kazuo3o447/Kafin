# FRED API (Federal Reserve Economic Data)

Base-URL: `https://api.stlouisfed.org/fred`
Auth: Query-Parameter `api_key={FRED_API_KEY}`
Rate-Limit: 120 Requests/Minute
Docs: https://fred.stlouisfed.org/docs/api/fred/
Kostenlos, API-Key erforderlich: https://fred.stlouisfed.org/docs/api/api_key.html

## Konfiguration
- FRED_API_KEY: aus `.env` oder den Container-Umgebungsvariablen laden

## Fehlerverhalten

- Bei temporären FRED-5xx-Fehlern versucht das Backend den Request bis zu 3x erneut.
- Log-Ausgaben redigieren den `api_key`-Parameter, damit keine Secrets im Log landen.
- Wenn FRED danach weiterhin fehlschlägt, liefert der Macro-Snapshot `None`-Werte für die betroffene Serie und das System läuft weiter.

## Genutzter Endpoint

### Series Observations
GET /series/observations?series_id={ID}&api_key={key}&sort_order=desc&limit=1&file_type=json

Response-Feld: `observations` (Array)
Jedes Element:
- date (str): Datum YYYY-MM-DD
- value (str): Wert als String (muss zu float konvertiert werden, "." bei fehlenden Daten)

## Genutzte Serien-IDs

| Serie | ID | Beschreibung | Frequenz |
|-------|-----|-------------|----------|
| Fed Funds Rate | FEDFUNDS | Aktueller Leitzins | Monatlich |
| VIX | VIXCLS | CBOE Volatility Index | Täglich |
| High-Yield Credit Spread | BAMLH0A0HYM2 | ICE BofA HY OAS | Täglich |
| 10Y-2Y Yield Spread | T10Y2Y | Treasury Yield Curve | Täglich |
| Dollar Index | DTWEXBGS | Trade Weighted USD Broad | Täglich |
| M2 Geldmenge | M2SL | M2 Money Stock | Monatlich |

## Interpretation für Makro-Regime

- VIX < 15: Markt entspannt. VIX 15-25: Erhöhte Vorsicht. VIX > 30: Panik.
- Credit Spread < 300 Bp: Normal. > 300 Bp: Stress. > 500 Bp: Rezessionsgefahr.
- T10Y2Y > 0: Yield Curve positiv. ≈ 0: Flach. < 0: Invertiert (Rezessionssignal).
- FEDFUNDS fallend: Fed senkt → bullisch. Steigend: Fed strafft → bärisch.

## Python-Beispiel
```python
import httpx

url = "https://api.stlouisfed.org/fred/series/observations"
params = {
    "series_id": "VIXCLS",
    "api_key": FRED_API_KEY,
    "sort_order": "desc",
    "limit": 1,
    "file_type": "json"
}
response = await client.get(url, params=params)
value = float(response.json()["observations"][0]["value"])
```
