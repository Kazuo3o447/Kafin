# Kafin — API-Dokumentationen
## Für docs/apis/ im Repository

Diese Dateien einzeln in docs/apis/ ablegen oder per Prompt an den Agenten übergeben.

---

## DATEI: docs/apis/finnhub.md

```markdown
# Finnhub API

Base-URL: `https://finnhub.io/api/v1`
Auth: Query-Parameter `token={FINNHUB_API_KEY}`
Rate-Limit: 60 Calls/Minute (Free Tier)
Docs: https://finnhub.io/docs/api

## Genutzte Endpoints

### Earnings Calendar
GET /calendar/earnings?from={YYYY-MM-DD}&to={YYYY-MM-DD}&token={key}

Response-Feld: `earningsCalendar` (Array)
Jedes Element:
- symbol (str): Ticker
- date (str): Earnings-Datum
- epsEstimate (float|null): EPS-Konsens
- epsActual (float|null): Tatsächliches EPS (erst nach Meldung)
- revenueEstimate (float|null): Umsatz-Konsens
- revenueActual (float|null): Tatsächlicher Umsatz
- hour (str): "bmo" (before market open) oder "amc" (after market close)

### Company News
GET /company-news?symbol={TICKER}&from={YYYY-MM-DD}&to={YYYY-MM-DD}&token={key}

Response: Array von Nachrichten
Jedes Element:
- headline (str): Schlagzeile
- summary (str): Zusammenfassung
- category (str): Kategorie (z.B. "company")
- url (str): Link zum Artikel
- datetime (int): Unix-Timestamp
- source (str): Quelle

### Short Interest
GET /stock/short-interest?symbol={TICKER}&token={key}

Response-Feld: `data` (Array, sortiert nach Datum absteigend)
Jedes Element:
- shortInterest (int): Anzahl Short-Aktien
- volume (int): Durchschnittliches Tagesvolumen
- shortPercentOfFloat (float): Short Interest als % des Floats

Berechnung Days-to-Cover: shortInterest / volume
Trend: Vergleiche die letzten 4 Datenpunkte

### Insider Transactions
GET /stock/insider-transactions?symbol={TICKER}&token={key}

Response-Feld: `data` (Array)
Jedes Element:
- name (str): Name des Insiders
- share (int): Anzahl Aktien (positiv=Kauf, negativ=Verkauf)
- transactionDate (str): Datum YYYY-MM-DD
- transactionType (str): z.B. "P-Purchase", "S-Sale"

Cluster-Erkennung: 3+ verschiedene Insider innerhalb 14 Tagen = Cluster

### Quote (Aktueller Kurs)
GET /quote?symbol={TICKER}&token={key}

Response:
- c (float): Current Price
- h (float): High
- l (float): Low
- o (float): Open
- pc (float): Previous Close
- dp (float): Percent Change
```

---

## DATEI: docs/apis/fmp.md

```markdown
# Financial Modeling Prep (FMP) API

Base-URL: `https://financialmodelingprep.com/api/v3`
Auth: Query-Parameter `apikey={FMP_API_KEY}`
Rate-Limit: 300 Calls/Minute (Starter)
Docs: https://site.financialmodelingprep.com/developer/docs

## Genutzte Endpoints

### Company Profile
GET /profile/{TICKER}?apikey={key}

Response: Array mit einem Element
- symbol (str): Ticker
- companyName (str): Name
- sector (str): Sektor
- industry (str): Branche
- mktCap (float): Marktkapitalisierung
- price (float): Aktueller Kurs

### Key Metrics (TTM)
GET /key-metrics-ttm/{TICKER}?apikey={key}

Response: Array mit einem Element
- peRatioTTM (float): P/E Ratio
- priceToSalesRatioTTM (float): P/S Ratio
- marketCapTTM (float): Marktkapitalisierung
- dividendYieldTTM (float): Dividendenrendite

### Analyst Estimates
GET /analyst-estimates/{TICKER}?period=quarter&limit=4&apikey={key}

Response: Array (pro Quartal ein Element)
- date (str): Datum
- estimatedRevenueAvg (float): Umsatz-Konsens
- estimatedEpsAvg (float): EPS-Konsens
- estimatedRevenueHigh/Low (float): Spannbreite
- estimatedEpsHigh/Low (float): Spannbreite
- numberAnalystEstimatedRevenue (int): Anzahl Analysten

### Earnings Surprises
GET /earnings-surprises/{TICKER}?apikey={key}

Response: Array (historische Quartale)
- date (str): Earnings-Datum
- actualEarningResult (float): Tatsächliches EPS
- estimatedEarning (float): Erwartetes EPS
Berechnung: surprise_percent = ((actual - estimated) / abs(estimated)) * 100

### Earnings Calendar
GET /earning_calendar?from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={key}

Response: Array
- symbol (str): Ticker
- date (str): Datum
- eps (float|null): Tatsächliches EPS
- epsEstimated (float): Geschätztes EPS
- revenue (float|null): Tatsächlicher Umsatz
- revenueEstimated (float): Geschätzter Umsatz
- time (str): "bmo" oder "amc"

### S&P 500 Constituents
GET /sp500_constituent?apikey={key}

Response: Array aller S&P 500 Unternehmen
- symbol, name, sector, subSector
```

---

## DATEI: docs/apis/fred.md

```markdown
# FRED API (Federal Reserve Economic Data)

Base-URL: `https://api.stlouisfed.org/fred`
Auth: Query-Parameter `api_key={FRED_API_KEY}`
Rate-Limit: 120 Requests/Minute
Docs: https://fred.stlouisfed.org/docs/api/fred/
Kostenlos, API-Key erforderlich: https://fred.stlouisfed.org/docs/api/api_key.html

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
```

---

## DATEI: docs/apis/deepseek.md

```markdown
# DeepSeek API

Base-URL: `https://api.deepseek.com` (oder `https://api.deepseek.com/v1` für OpenAI-Kompatibilität)
Auth: Header `Authorization: Bearer {DEEPSEEK_API_KEY}`
Modell: `deepseek-chat` (DeepSeek-V3.2, 128K Kontext)
Docs: https://api-docs.deepseek.com/
Pricing: $0.28/M Input-Tokens, $0.42/M Output-Tokens (Stand März 2026)

## Genutzter Endpoint

### Chat Completions
POST /chat/completions

Request-Body:
```json
{
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "System-Prompt"},
        {"role": "user", "content": "User-Prompt"}
    ],
    "temperature": 0.3,
    "max_tokens": 4096,
    "stream": false
}
```

Response:
```json
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "Antwort-Text"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 150,
        "completion_tokens": 500,
        "total_tokens": 650
    }
}
```

## Wichtige Parameter
- temperature: 0.3 für konsistente Analysen (nicht zu kreativ)
- max_tokens: 4096 für Reports
- stream: false (wir brauchen kein Streaming)

## Für JSON-Output
Im System-Prompt angeben: "Antworte NUR mit validem JSON, ohne Markdown-Backticks."
Alternativ: `response_format: {"type": "json_object"}` im Request

## Fehler-Handling
- 429: Rate Limit → Retry mit Backoff
- 401: Ungültiger Key
- 500/502/503: Server-Fehler → Retry

## Python-Beispiel
```python
import httpx

headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.3,
    "max_tokens": 4096
}
response = await client.post(
    "https://api.deepseek.com/chat/completions",
    headers=headers,
    json=payload
)
text = response.json()["choices"][0]["message"]["content"]
```
```

---

## DATEI: docs/apis/kimi.md

```markdown
# Kimi / Moonshot AI API

Base-URL: `https://api.moonshot.ai/v1`
Auth: Header `Authorization: Bearer {KIMI_API_KEY}`
Modelle: `moonshot-v1-auto` (automatische Kontextauswahl), `kimi-k2.5` (neuestes)
Kontext: Bis 256K Tokens (K2.5)
Docs: https://platform.moonshot.ai/docs/api/chat
API-Format: OpenAI-kompatibel

## Genutzter Endpoint

### Chat Completions
POST /chat/completions

Request-Body (identisch mit OpenAI-Format):
```json
{
    "model": "moonshot-v1-auto",
    "messages": [
        {"role": "system", "content": "System-Prompt"},
        {"role": "user", "content": "User-Prompt (kann sehr lang sein, bis 256K)"}
    ],
    "temperature": 0.6,
    "max_tokens": 8192
}
```

Response (identisch mit OpenAI-Format):
```json
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "Antwort-Text"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 12000,
        "completion_tokens": 2000,
        "total_tokens": 14000
    }
}
```

## Besonderheiten
- Temperature nur 0-1 (nicht 0-2 wie bei OpenAI)
- Empfohlene Temperature: 0.6 für Reasoning, 0.3 für strukturierte Analysen
- 256K Kontext → Ideal für ganze Earnings-Call-Transkripte
- OpenAI Python SDK funktioniert direkt: base_url="https://api.moonshot.ai/v1"

## Einsatz in Kafin
- Stufe 2 der KI-Kaskade: Tiefenanalyse von Earnings-Transkripten
- Nur für Audit-Reports (5-8 pro Woche), nicht für Massen-Screening
- Pricing: $0.60/M Input, $2.50/M Output

## Python-Beispiel
```python
import httpx

headers = {
    "Authorization": f"Bearer {KIMI_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "moonshot-v1-auto",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript_text}  # Kann 50K+ Tokens sein
    ],
    "temperature": 0.6,
    "max_tokens": 8192
}
response = await client.post(
    "https://api.moonshot.ai/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=60.0  # Längerer Timeout für große Kontexte
)
text = response.json()["choices"][0]["message"]["content"]
```
```

---

## DATEI: docs/apis/coinglass.md

```markdown
# CoinGlass API

Base-URL: `https://open-api-v3.coinglass.com/api` (V3) oder `https://open-api-v4.coinglass.com/api` (V4)
Auth: Header `CG-API-KEY: {COINGLASS_API_KEY}`
Rate-Limit: 30 Calls/Minute (Hobbyist, $29/Monat)
Docs: https://docs.coinglass.com/reference/getting-started-with-your-api
Hinweis: V4 ist aktuell empfohlen, V3 ist deprecated aber noch verfügbar

## Genutzte Endpoints

### Open Interest (aggregiert)
GET /futures/openInterest/chart?symbol=BTC&interval=1d&limit=30

Response: Array mit historischen OI-Daten
- t (int): Timestamp
- o (float): Open Interest in USD

### Funding Rate
GET /futures/funding-rates/latest

Response: Array
- symbol (str): z.B. "BTC"
- uMarginList (Array): Funding Rates pro Exchange
  - exchangeName (str)
  - rate (float): Aktuelle Funding Rate

### Liquidation Map
GET /futures/liquidation/map?symbol=BTC

Response:
- data (Object): Keys sind Preis-Levels, Values sind Arrays mit:
  - [0]: Liquidation-Preis
  - [1]: Liquidation-Volumen in USD
  - [2]: Leverage-Ratio

### Liquidation Aggregated History
GET /futures/liquidation/aggregated-history?symbol=BTC&interval=1h&limit=24

Response: Historische Liquidationsdaten
- Longs und Shorts getrennt

### Long/Short Ratio
GET /futures/longShort/chart?symbol=BTC&interval=1d&limit=7

Response: Array
- longRate (float): Long-Anteil
- shortRate (float): Short-Anteil
- longShortRatio (float): Ratio

## Interpretation für Bitcoin-Report

- Funding Rate > 0.05%: Extrem überhebelt long → Warnung
- Funding Rate < -0.03%: Überhebelt short → Warnung
- OI steigt bei seitwärts Preis: Squeeze-Aufbau
- OI-Drop > 10% plötzlich: Cascade-Liquidation

## Python-Beispiel
```python
import httpx

headers = {
    "CG-API-KEY": COINGLASS_API_KEY,
    "Content-Type": "application/json"
}
response = await client.get(
    "https://open-api-v3.coinglass.com/api/futures/funding-rates/latest",
    headers=headers
)
data = response.json()["data"]
btc_funding = [x for x in data if x["symbol"] == "BTC"][0]
```
```

---

## DATEI: docs/apis/supabase.md

```markdown
# Supabase

Dashboard: https://supabase.com/dashboard
Docs: https://supabase.com/docs
Python-Client: `supabase-py` (bereits in requirements.txt)

## Konfiguration
- SUPABASE_URL: Projekt-URL (z.B. https://xxxx.supabase.co)
- SUPABASE_KEY: anon/public Key oder service_role Key

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
```
