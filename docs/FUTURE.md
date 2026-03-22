# KAFIN — Zukunftsvisionen & Technical Debt

*Erstellt: 21. März 2026*
*Prinzip: Trading-First statt Data-First*

---

## Kürzlich abgeschlossen (v5.9.1)

### ✅ P1b Enhanced mit Robustness
- **FMP Grade-Keys**: Robuste Normalisierung und Sample Gates
- **Recency-Weighting**: Neuere Analyst-Grades stärker gewichtet
- **Freshness-Filter**: Management-Events nur 30 Tage relevant
- **Admin-Tools**: Score Backfill für Watchlist-History
- **Einschränkungen dokumentiert**: Watchlist vs Live-Scoring

---

## Phase 1 — Signal-First UX
Ideen, geplante Features und technische Schulden die bekannt aber noch nicht implementiert sind.
Wird bei jeder Session gepflegt.

---

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EINTRAG 1: Index-Chartanalyse auf Markets
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🟠 FEATURE: Index-Chartanalyse auf Markets-Dashboard

**Warum:**
SPY -1.85% ist eine Zahl. "SPY testet gerade den
SMA200 bei $562 — letztes Mal führte das zu einem
Bounce, diesmal bricht die Marktbreite weg" ist
eine Entscheidungsgrundlage. Der Trader muss beim
Öffnen des Markets-Dashboards sofort einschätzen
können: intakter Trend oder struktureller Bruch?

**Was konkret:**
Jeder Index (SPY, QQQ, DAX, Nikkei etc.) bekommt
einen "Analyse"-Button der on-demand aufgerufen wird.
Ergebnis: Chart-Analyse mit Fokus auf:
  - Trendintegrität: Ist der Uptrend intakt oder bricht er?
  - Key Level: Welches Level ist gerade entscheidend?
  - Nächster Support/Widerstand mit Erklärung
  - Kein Entry/Stop/Target (macht für Indizes
    wenig Sinn) — stattdessen Regime-Kontext

**Technisch:**
chart_analyst.py bereits vorhanden — für Index-Ticker
(SPY, ^GDAXI etc.) aufrufen. DeepSeek-Prompt
anpassen: kein Trade-Setup, stattdessen
strukturelle Marktanalyse.
Cache: 600s (Indizes bewegen sich langsamer).
UI: kleiner "Analysieren"-Button pro Index-Karte.

**Aufwand:** ~2h | **Modell:** SWE-1.5

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EINTRAG 2: Chart-Analyse Begründung + Boden/Turnaround
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔴 KRITISCH: Chart-Analyse Begründung (Anti-Falling-Knife)

**Warum:**
"Entry $842, Stop $815, Target $920" — das
beantwortet NICHT die wichtigste Frage des Traders:
"Warum diese Levels? Greife ich ins fallende Messer?
Wo ist der echte Boden? Was muss passieren damit
sich der Trend dreht?"

Ohne Begründung sind Zahlen wertlos. Ein
institutioneller Trader würde nie eine Position
eingehen ohne die Struktur hinter dem Level zu
kennen.

**Was konkret — neue Felder in chart_analyst.py:**

  trend_context: "Abwärtstrend seit 3 Monaten. Death
    Cross (SMA50 unter SMA200). 23% unter 52W-Hoch."

  why_entry: "Entry-Zone liegt zwischen 20T-Support
    ($X) und letztem Swing-Tief ($Y). Zone wo in den
    letzten 3 Wochen Käufer aufgetaucht sind."

  why_stop: "Stop knapp unter $815 = letztes
    signifikantes Swing-Tief vom [Datum]. Bruch würde
    nächste Unterstützungszone bei $X aktivieren."

  floor_scenario: "Nächster harter Support: $780
    (52W-Tief). Darunter kein struktureller Support
    bis $720 (Pre-Earnings-Base Juli 2024)."

  turnaround_conditions: "Bullishes Signal wenn:
    (1) Schlusskurs über SMA50 bei $X mit Volumen
    >1.5x Durchschnitt ODER (2) positive Überraschung
    beim nächsten Earnings + Guidance-Erhöhung."

  falling_knife_risk: "HOCH — Abwärtstrend intakt,
    kein Volumensignal für Bodenbildung, Insiders
    verkaufen. Warte auf Bestätigung."

**Technisch:**
DeepSeek-Prompt in chart_analyst.py erweitern.
Neue Felder im JSON-Schema hinzufügen.
Frontend: aufklappbarer "Warum?"-Block unter
den Levels im Trade-Setup-Block.

**Aufwand:** ~2h | **Modell:** Sonnet 4.5
**Priorität:** Höchste — direkt umsetzbar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EINTRAG 3: Earnings-Kalender als Battle Card
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🟠 FEATURE: Earnings Battle Card

**Warum:**
Der Earnings-Kalender ist das wichtigste Trading-
Werkzeug der Woche — und zeigt aktuell nur Ticker
plus Datum. Ein Profitrader braucht in 10 Sekunden
pro Eintrag: "Kann ich das traden? Was ist das
Risiko? Was erwartet der Markt?"

**Was konkret — pro Earnings-Eintrag:**

  SETUP-AMPEL (sofort sichtbar):
    Grün = tradeable Setup (Opp hoch, Torp niedrig)
    Amber = gemischtes Signal
    Rot = zu riskant oder kein Setup

  ERWARTUNGEN:
    EPS-Konsens + Revenue-Konsens
    Expected Move (±%) aus IV — "Markt erwartet ±8.2%"
    Put/Call Ratio — ist der Markt bullisch/bärisch positioniert?

  TRACK RECORD (Ampel-Farbe):
    "6/8 Quartale geschlagen · Ø +11% Surprise"
    Letzte Reaktion: "+7.3% nach letztem Beat"

  POSITIONIERUNGS-RISIKO:
    Preis-Performance letzte 30T:
    "+23% — Buy-the-Rumor-Risiko" (amber Warnung)

  PRE-EARNINGS SENTIMENT:
    News-Stimmung letzte 7T (bereits vorhanden)

  EMPFEHLUNG (aus Opp/Torp):
    "Setup: KAUFEN mit engem Stop" /
    "Setup: MEIDEN — Torpedo zu hoch" /
    "Setup: BEOBACHTEN"

**Technisch:**
Earnings-Radar Endpoint bereits vorhanden mit
Opp/Torp, beats_of_8, avg_surprise_pct,
pre_earnings_sentiment.
Fehlt: expected_move (aus IV — schon in Research
berechnet, in quick_snapshot ergänzen),
price_change_30d (in quick_snapshot ergänzen),
put_call_ratio.
Frontend: kompakte "Battle Card" pro Eintrag
statt einfacher Listenzeile.

**Aufwand:** ~3h | **Modell:** Sonnet 4.5

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EINTRAG 4: Dashboard als Morning Brief
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🟠 FEATURE: Dashboard → Morning Brief

**Warum:**
Das aktuelle Dashboard ist eine Datenseite.
Ein Trader öffnet die Plattform morgens mit einer
Frage: "Was muss ich heute wissen und tun?"
Das Dashboard muss diese Frage in 10 Sekunden
beantworten — nicht in 10 Minuten Scrollen.

**Was konkret — 5 Sektionen:**

  1. REGIME-PULSE (1 Zeile, ganz oben):
     Composite-Regime + Score + Dominant-Faktor
     "Risk-Off · Score −4.2 · Treiber: VIX 28.4"
     Direkt aus calcCompositeRegime() — kein API-Call

  2. AKTIVE ALERTS (max. 5, priorisiert):
     Material-News, Torpedo-Alarm, Earnings diese Woche
     Identisch zu Watchlist-Alert-Streifen —
     wiederverwendete Logik

  3. EARNINGS DIESE WOCHE (kompakt):
     Max. 3 Watchlist-Ticker mit Countdown + Setup-Ampel
     Link → Earnings-Radar für Details

  4. BESTE SETUPS JETZT (2 Kacheln):
     Watchlist-Ticker mit höchstem Opp-Score
     + Watchlist-Ticker mit höchstem Torpedo
     (damit ich weiß was zu traden UND was zu meiden)

  5. OVERNIGHT-KONTEXT (3 Zahlen):
     SPY, VIX, Credit Spread — aktuelle Werte
     mit 1T-Veränderung

**Was wegfällt:**
  - Generische Index-Cards (schon auf Markets)
  - Opportunities-Block (undifferenziert)
  - Langer Briefing-Text als Hauptinhalt
    (bleibt, aber kompakter unten)

**Technisch:**
Alle Daten bereits vorhanden:
  - Watchlist enriched (Scores, Earnings, Alerts)
  - Macro snapshot (VIX, Credit Spread)
  - Market overview (SPY)
Kein neuer Backend-Endpoint nötig.
Reine Frontend-Überarbeitung.

**Aufwand:** ~3h | **Modell:** Sonnet 4.5

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSCHLUSS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

---

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EINTRAG: PostgreSQL Migration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔴 ARCHITEKTUR: Supabase → Lokales PostgreSQL

**Warum:**
Kafin läuft lokal auf dem NUC. Supabase ist
eine externe Cloud-Datenbank — das bedeutet:
- 20-80ms Extra-Latenz bei JEDER DB-Query
  (Internet-Roundtrip statt lokaler Socket)
- Externe Abhängigkeit: Supabase-Ausfall =
  Kafin funktioniert nicht
- Rate-Limits auf Free-Tier
- Sensible Trading-Daten auf fremden Servern
- Kein "Alles-in-einem-Paket" Deployment

**Ziel:**
PostgreSQL 16 als Docker-Container im selben
docker-compose.yml wie Backend, Frontend, n8n.
Lokale Verbindung via Unix-Socket oder localhost.
Keine externe Abhängigkeit mehr.

**Aufwand:** ~3-4 Stunden, einmaliger Migrations-Tag.
**Zeitpunkt:** Nach stabilem Entwicklungsstand —
NICHT mitten in aktiver Feature-Entwicklung.

**Implementierungsplan (für Windsurf ausführbar):**

SCHRITT 1 — docker-compose.yml: PostgreSQL ergänzen:
```yaml
postgres:
  image: postgres:16-alpine
  container_name: kafin-postgres
  environment:
    POSTGRES_DB: kafin
    POSTGRES_USER: kafin
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-kafin_local}
  volumes:
    - ./data/postgres:/var/lib/postgresql/data
    - ./backend/init_db.sql:/docker-entrypoint-initdb.d/init.sql:ro
  ports:
    - "5432:5432"
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U kafin"]
    interval: 10s
    timeout: 5s
    retries: 5
```

SCHRITT 2 — backend/app/config.py: DB-URL ergänzen:
```python
database_url: str = "postgresql://kafin:kafin_local@postgres:5432/kafin"
```

SCHRITT 3 — backend/app/db.py: neue Verbindungsklasse:
```python
import psycopg2
from backend.app.config import settings

def get_db_connection():
    return psycopg2.connect(settings.database_url)

# Async-Version mit asyncpg:
import asyncpg
async def get_async_db():
    return await asyncpg.connect(settings.database_url)
```

SCHRITT 4 — Alle get_supabase_client() Aufrufe
ersetzen durch get_db_connection().
Supabase-spezifische Syntax (.table().select().execute())
durch Standard-SQL ersetzen.

Betroffene Dateien (alle grep nach get_supabase_client):
  - backend/app/main.py (häufig)
  - backend/app/memory/watchlist.py
  - backend/app/memory/short_term.py
  - backend/app/memory/long_term.py
  - backend/app/analysis/report_generator.py

SCHRITT 5 — Datenmigration aus Supabase:
```bash
# In Supabase Dashboard: Settings → Database → Backups
# oder via pg_dump gegen Supabase Connection String:
pg_dump "postgresql://[supabase-url]" > kafin_backup.sql
psql "postgresql://kafin:kafin_local@localhost:5432/kafin" < kafin_backup.sql
```

SCHRITT 6 — .env: SUPABASE_URL + SUPABASE_KEY entfernen.
SCHRITT 7 — Supabase-Projekt pausieren/löschen.

**Abhängigkeiten:**
- psycopg2-binary oder asyncpg in requirements.txt
- init_db.sql bereits vorhanden (backend/app/init_db.py
  muss als .sql exportiert werden)
- docker-compose.yml: backend depends_on: postgres

**Erwartete Verbesserungen nach Migration:**
- Ladezeit enriched Watchlist: −30-50ms pro Query
- Audit-Report Generierung: −100-200ms (mehrere Queries)
- Keine Rate-Limit-Fehler mehr
- Offline-Betrieb vollständig möglich
- Deployment: ein einziger docker-compose up

**Risiken:**
- Datenverlust wenn Migration nicht korrekt
  → Backup VOR Migration Pflicht
- SQL-Syntax-Anpassungen (Supabase-SDK vs. raw SQL)
- asyncpg/psycopg2 Entscheidung treffen

**Empfehlung:** psycopg2 für Sync-Calls (bestehender Code),
asyncpg für neue async-Endpoints. SQLAlchemy als ORM
ist Overkill für diesen Use-Case — raw SQL reicht.

**Timing:** Erst wenn Research Dashboard P1-P3,
Watchlist v2 und Markets Dashboard stabil laufen.
Dann als dedizierter "Infrastructure Day".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

---

## ✅ IMPLEMENTIERT: Markets Dashboard v2 (/markets)
- **Granulare Refresh-Zyklen**: 9 Blöcke mit individuellen Intervallen (60s-30min)
- **Block 1: Globale Indizes**: SPY, QQQ, DIA, IWM, DAX, Euro Stoxx 50, Nikkei 225, MSCI World
- **Block 2: Sektor-Rotation**: 11 Sektoren mit 5d Performance und Ranking
- **Block 3: Marktbreite**: S&P 500 Top 50 statt Dow 30, mit breadth_index
- **Block 4: Makro-Dashboard**: Fed Rate, VIX, Credit Spread, Yield Curve
- **Block 5: Cross-Asset Signale**: Risk Appetite, VIX-Struktur, Credit-Signal
- **Block 6: Marktnachrichten + FinBERT**: Kategorisierte News mit Sentiment-Scores
- **Block 7: Wirtschaftskalender**: 48h Events mit Impact-Bewertung
- **Block 8: KI-Markt-Audit**: DeepSeek Regime-Einschätzung auf Knopfdruck
- **Block 9: Makro-Proxys**: VIX, TLT, UUP, GLD, USO mit RSI
- **Promise.allSettled**: Robuste Parallel-Fetches für alle Blöcke
- **Timestamp-Delta**: "vor 5 min" Anzeige mit Stale-Warnungen
- **BlockError**: Fallback-Komponente für fehlgeschlagene API-Calls

## 🟡 MARKETS: Marktbreite 5T/20T Verlauf
Aktuell: pct_above_sma50_5d_ago = None (Placeholder).
Lösung: Täglichen Breadth-Wert in Supabase speichern.
Neue Tabelle: market_breadth_history (date, pct_sma50, pct_sma200).
n8n: täglich um 22:00 speichern.
Aufwand: ~2h, SWE-1.5.

## 🟡 FUTURE: General News Endpoint
GET /api/news/general fehlt noch.
Backend: `get_general_market_news()` existiert in `backend/app/data/market_overview.py`.
Endpoint in `backend/app/main.py` verdrahten und optional `api.ts` ergänzen.
Aufwand: 30 Minuten, SWE-1.5.

## 🟡 FUTURE: Marktbreite verbessern
Aktuell: 30 Dow-Titel als Proxy.
Besser: S&P 500 Advance-Decline-Linie via ^SPXAD (yfinance).
`yf.Ticker("^SPXAD").history(period="1mo")` — testen ob verfügbar.
Aufwand: 30 Minuten wenn ^SPXAD korrekt liefert.

## 🟡 FUTURE: Fear & Greed Score
Berechenbar aus: VIX-Level, Put/Call Ratio, Junk Bond Demand (HYG),
Market Momentum (SPY vs SMA125), Safe Haven Demand (TLT vs SPY),
Stock Price Strength (new 52W highs vs lows).
Zeigt 0-100 Score analog CNN Fear & Greed.
Aufwand: ~3h, SWE-1.5.

## 🟡 AUS DEM REVIEW OFFEN

### Zentralisierung von Signal-Konstanten
- `SECTOR_TO_ETF` ist aktuell noch in `scoring.py`, `main.py` und `report_generator.py` dupliziert.
- Ziel: eine autoritative Quelle oder ein Shared-Helper für Mapping + Signal-Labels.

### Zentrale Cache-Invalidierung
- News-Writepfade invalidieren derzeit die abhängigen Caches noch inline.
- Ziel: ein gemeinsamer Helper für Research-, Watchlist- und Earnings-Invalidierung.

### Gemeinsamer TickerContext
- `api_research_dashboard` und `generate_audit_report()` bauen den Data-Context noch separat zusammen.
- Ziel: ein gemeinsames Context-Objekt, damit Scoring, Audit und UI dieselben Datenfelder nutzen.

### Composite-Regime kalibrieren
- Der Markets-Header ist live, braucht aber historische Kalibrierung auf reale Risk-On/Risk-Off-Phasen.
- Ziel: Schwellen und Gewichtungen gegen Marktregime-Phasen backtesten und dann stabilisieren.

### Marktbreite-Historie
- `pct_above_sma50_5d_ago` und `pct_above_sma50_20d_ago` sind noch Platzhalter.
- Ziel: tägliche Breadth-Historie persistieren, damit der Trend sauberer sichtbar wird.

### Firmenprofil als Research-Modul
- P1c ist weiterhin offen: CEO, Beschreibung, Mitarbeiterzahl und Gründung sollten als eigener Block im Research-Dashboard erscheinen.
- Zusätzlich sollte der Firmenkontext in den Audit-Prompt einfließen.

---

## 🟡 INTRADAY — VWAP

**Was:** Volume Weighted Average Price — Fair-Value-Linie für Daytrader.
Long über VWAP = bullish Intraday-Bias. Short darunter = bearish.

**Warum noch nicht:** VWAP wird täglich neu berechnet und braucht
1-Minuten-Daten. yfinance liefert das technisch mit:
  `yf.Ticker(ticker).history(period="1d", interval="1m")` 
Das sind 390 Datenpunkte pro Ticker pro Request — vertretbar
für manuelle Abfragen, aber zu teuer für automatische Batch-Updates.

**Implementierung wenn bereit:**
- Neuer Endpoint: GET /api/data/vwap/{ticker}
- Eigene Cache-Strategie: 5-Minuten-TTL (Intraday-Daten)
- Frontend: StatCell im "Technisches Bild" Block
- Formel: sum(typical_price * volume) / sum(volume)
  wobei typical_price = (High + Low + Close) / 3

**Aufwand:** ~2h, SWE-1.5, kein Review nötig.

---

## 🔴 LEVEL II ORDERBOOK

**Was:** Bid-Ask-Tiefe — zeigt große Orders als Support/Resistance.
"Große Bid-Blöcke bei $X → starke Unterstützungszone"

**Warum nicht machbar kostenlos:**
Weder yfinance noch Finnhub Free liefern Orderbook-Tiefe.
Alternativen:
  - Interactive Brokers TWS API (braucht IB-Konto + Genehmigung)
  - Polygon.io Starter ($29/Mo) — Level 2 quotes für US-Aktien
  - Alpaca Markets Free — limitiertes Level 2 für US-Ticker

**Empfehlung:** Polygon.io Starter wenn Level II wirklich gebraucht.
Gibt auch VWAP, erweiterte Optionsdaten und Tick-Daten.
URL: https://polygon.io/dashboard/stocks/starter

**Aufwand:** ~1 Tag, Polygon.io Key nötig.

---

## 🟡 OPTIONEN OPEN INTEREST PRO STRIKE

**Was:** Welche Strike-Preise haben das meiste Open Interest?
→ "Max Pain" Berechnung, magnetische Support/Resistance-Level.
Hohe OI-Strikes = Kurse tendieren zu diesen Leveln vor Expiration.

**Warum noch nicht:** yfinance liefert OI pro Strike bereits
(option_chain), aber die Visualisierung und Max-Pain-Berechnung
fehlen im Frontend.

**Implementierung wenn bereit:**
- Backend: Neuer Endpoint GET /api/data/options-oi/{ticker}
  → Gibt Top-10 Strikes nach OI zurück (Calls + Puts getrennt)
- Frontend: Einfache Tabelle im "Analyst & Options" Block
- Max Pain Formel: Strike mit minimiertem Gesamtverlust aller Options

**Aufwand:** ~3h, SWE-1.5.

---

## 🟢 SYSTEM_LOGS CLEANUP (Technische Schuld)

**Was:** system_logs Tabelle wächst unbegrenzt.
Sentiment-Monitor und Peer-Monitor loggen jeden Alert.

**Lösung:** Supabase pg_cron Job:
  SELECT cron.schedule(
    'cleanup-system-logs',
    '0 3 * * 0',  -- Jeden Sonntag 03:00
    $$DELETE FROM system_logs WHERE created_at < NOW() - INTERVAL '30 days'$$
  );

**Aufwand:** 1 SQL-Statement, direkt in Supabase SQL Editor ausführen.

---

## 🟡 EARNINGS-KALENDER IM RESEARCH-DASHBOARD

**Was:** Nächste 5 Earnings-Termine aus dem gleichen Sektor
direkt im Research-Dashboard anzeigen.
"HIMS meldet in 12 Tagen — und diese Peers auch bald..."

**Warum noch nicht:** Earnings-Radar existiert, aber nicht
integriert in das Research-Dashboard.

**Aufwand:** ~1h, SWE-1.5.

---

## 🟡 WATCHLIST PRIO → RESEARCH AUTO-UPDATE

**Was:** Watchlist-Ticker mit Prio 1 sollen täglich 3x automatisch
ihren Research-Cache refreshen (force_refresh=true).
Derzeit macht das n8n nur für News und Reports, nicht für
den neuen Research-Endpoint.

**Implementierung:**
- n8n Workflow: täglich 08:00, 13:00, 18:00
- POST /api/data/research/{ticker}?force_refresh=true
  für alle Prio-1 Ticker aus der Watchlist

**Aufwand:** ~1h, SWE-1.5.

---

## 🟢 MACD HISTOGRAM VISUALISIERUNG

**Was:** MACD-Histogram als Mini-Balkendiagramm statt nur Zahl.
Grüne Balken = bullish, rote Balken = bearish, Trend erkennbar.

**Aufwand:** ~2h, SVG inline im StatCell.

---

## ✅ IMPLEMENTIERT (20. März 2026)

### 52-WOCHEN PREISSPANNE VISUALISIERUNG
Horizontaler Balken zeigt Position zwischen Jahrestief/hoch mit Farbgradient.
Implementiert in `components/visualizations/PriceRangeBar.tsx`.

### VOLUMEN-PROFIL CHART
20-Tage Volumen-Balkendiagramm mit Recharts, grün/rot Farbcodierung.
Implementiert in `components/visualizations/VolumeProfile.tsx`.
Backend: `/api/data/volume-profile/{ticker}`.

### PEG RATIO GAUGE
Halbkreis-Gauge für Bewertung (grün = günstig, rot = teuer).
Implementiert in `components/visualizations/PEGGauge.tsx`.

### TERMINAL → LOG VIEWER OVERHAUL
Vollbild-Terminal ersetzt durch dezenten Bottom-Drawer mit Hotkey `Cmd+J`.
Implementiert in `components/LogViewer.tsx`. `/terminal` Route entfernt.

### WATCHLIST PERFORMANCE OPTIMIZATIONS
Reloads eliminiert mit Optimistic Updates für CRUD-Operationen.
Ticker hinzufügen/entfernen/Web-Prio ändern sofort sichtbar, keine API-Calls mehr.

### WATCHLIST PERFORMANCE REVOLUTION
yfinance Cache + Enriched Cache für 55x schnellere Ladezeiten (2.3s statt 127s).

### WATCHLIST DATA DISPLAY FIX
Frontend umgestellt auf enriched API - alle Spalten jetzt sichtbar (1T % Opp Torp).

### RESEARCH UX IMPROVEMENTS
Firmenname verlinkt + bessere Loading States mit User Guidance.

---

*Zuletzt aktualisiert: 20. März 2026*
*Nächste Review: vor dem nächsten Major Feature*
