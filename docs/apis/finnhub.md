# Finnhub API

Base-URL: `https://finnhub.io/api/v1`
Auth: Query-Parameter `token={FINNHUB_API_KEY}`
Rate-Limit: 60 Calls/Minute (Free Tier)
Docs: https://finnhub.io/docs/api

## Konfiguration
- FINNHUB_API_KEY: d6mk689r01qi0ajmimf0d6mk689r01qi0ajmimfg

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

### Economic Calendar (NEU)
GET /calendar/economic?from={YYYY-MM-DD}&to={YYYY-MM-DD}&token={key}

Response-Feld: `economicCalendar` (Array)
Jedes Element:
- event (str): Event-Name (z.B. "US CPI MoM")
- country (str): Land (z.B. "US")
- date (str): Datum YYYY-MM-DD
- time (str): Zeitpunkt
- impact (str): Impact-Level ("low", "medium", "high")
- estimate (float|null): Erwartungswert
- actual (float|null): Tatsächlicher Wert
- unit (str): Einheit (z.B. "%", "K")

Filter: Nur `impact == "high"` und `country == "US"` werden verarbeitet.
Gespeichert unter Pseudo-Ticker `GENERAL_MACRO` im Short-Term Memory.
