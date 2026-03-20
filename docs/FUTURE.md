# KAFIN — Future Features & Technische Schulden

Dieses Dokument sammelt alle Ideen, geplanten Features und
technischen Schulden die bekannt aber noch nicht implementiert sind.
Wird bei jeder Session gepflegt.

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

---

*Zuletzt aktualisiert: 20. März 2026*
*Nächste Review: vor dem nächsten Major Feature*
