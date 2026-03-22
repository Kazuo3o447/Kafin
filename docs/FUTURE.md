# KAFIN — Zukunftsvisionen & Technical Debt

*Erstellt: 21. März 2026*
*Prinzip: Trading-First statt Data-First*

---

## Kürzlich abgeschlossen (v5.12.2)

### ✅ Index-Chartanalyse auf Markets
**Status: ✅ ERLEDIGT (22.03.2026) — v5.12.2**
- "⚡ Chart analysieren" Button pro Index-Karte
- On-demand DeepSeek Analyse mit Bias + Reasoning
- Cache 600s, Close Button für Analyse

### ✅ Chart-Analyse Begründung (Anti-Falling-Knife)
**Status: ✅ ERLEDIGT (22.03.2026) — v5.12.0**
- why_entry/stop, trend_context, floor_scenario
- falling_knife_risk mit prominenten Warn-Bannern
- Aufklappbarer "Begründung anzeigen" Block

### ✅ Earnings Battle Card
**Status: ✅ ERLEDIGT (22.03.2026) — v5.12.1**
- Setup-Ampel aus Opp+Torp Scores
- Expected Move mit Break-Even Levels
- Track Record + Buy-Rumor Warnung

### ✅ Dashboard Morning Brief
**Status: ✅ ERLEDIGT (22.03.2026) — v5.12.2**
- RegimePulse (1-Zeile) + AlertStrip + TopSetups
- Earnings Badges + Overnight-Kontext (SPY/VIX/CS)
- Aufklappbares Morning Briefing

---

## 🟠 FEATURE: Max Pain Kalkulation

**Warum:**
Max Pain ist der Preis bei Optionsverfall wo
Optionskäufer den maximalen Verlust erleiden —
Market Maker haben Anreiz den Kurs dorthin zu
treiben. Starker kurzfristiger Reversal-Indikator
vor monatlichem/wöchentlichem Verfallstag.

**Was konkret:**
yfinance.option_chain() bereits integriert.
Daraus pro Verfallsdatum berechnen:
  max_pain_price = Preis wo (Calls OI * (price - strike))
    + (Puts OI * (strike - price)) minimal ist
  oi_heatmap: Strikes mit höchstem Open Interest
  put_call_oi_ratio: Gesamtes Put OI / Call OI

Anzeige: Research-Dashboard + Earnings Battle Card.
Telegram-Alert wenn Kurs stark vom Max Pain abweicht
(>5%) — möglicher Magnet-Effekt.

**Technisch:**
Reines Backend. yfinance option_chain() → pandas.
Kein neuer API-Key. Cache 4h (OI ändert sich täglich).
Neuer Endpoint: GET /api/data/max-pain/{ticker}

**Aufwand:** ~2h | **Modell:** SWE-1.5

---

## 🟠 FEATURE: Pre/Post-Market Kursdaten

**Warum:**
Earnings-Reaktionen passieren After-Hours.
Aktuell sieht der Trader die Reaktion erst am
nächsten Handelstag im Chart. Mit prepost=True
in yfinance history() bekommt man die After-Hours
und Pre-Market Kurse kostenlos.

**Was konkret:**
  1. Chart-Endpoint (OHLCV): prepost=True ergänzen
     damit After-Hours Balken im Chart sichtbar sind
  2. Earnings Battle Card: "Letzte After-Hours Reaktion"
     aus post_earnings_review ergänzen
  3. Research Dashboard: Pre-Market Kurs wenn Markt
     noch nicht offen (08:00-09:30 ET)

**Technisch:**
  yf.Ticker(t).history(period="5d", prepost=True)
  Bereits in chart_endpoint.py — Parameter ergänzen.
  Pre-Market Kurs: fast_info hat
    pre_market_price / post_market_price Attribute.

**Aufwand:** ~1h | **Modell:** SWE-1.5

---

## 🟠 FEATURE: Post-Earnings Kontext-Alert (Telegram)

**Warum:**
"HIMS schlägt EPS um +15% aber fällt -4% AH" —
das ist ein klassisches Torpedo-nach-Beat-Setup.
Der Trader muss das sofort wissen mit Kontext:
ist das eine Kaufgelegenheit oder der Beginn eines
Abverkaufs? Aktuell sendet der Torpedo-Monitor nur
einfache Warnungen ohne Kontext.

**Was konkret:**
Nach Earnings-Meldung (post_earnings_review läuft):
Telegram-Alert mit diesem Kontext:

  🎯 HIMS — Earnings Beat
  EPS: $0.08 vs $0.07 Konsens (+14%)
  Revenue: $530M vs $498M (+6%)

  📊 Marktreaktion (AH): -4.2%
  IV vorher: 45% | Expected Move war: ±8%
  → Reaktion INNERHALB Expected Move

  📈 Historisches Setup-Muster:
  Beat + AH-Rückgang: 4 von 6 Malen +5%
  in den nächsten 5 Handelstagen

  RSI (14): 38 — überverkauft
  Opp-Score: 7.4 | Torpedo-Score: 3.1

  ⚡ Mögliche Kaufgelegenheit — prüfen!

**Technisch:**
post_earnings_review.py bereits vorhanden.
yfinance prepost=True für AH-Reaktion.
EarningsHistory aus Supabase für historisches Muster.
Telegram-Format verbessern.

**Aufwand:** ~3h | **Modell:** Sonnet / SWE-1.5

---

## 🟢 FEATURE: FINRA Short Volume (kostenlos)

**Warum:**
FMP Short Interest (täglich aktualisiert) bereits
integriert. FINRA veröffentlicht TÄGLICH das
Short-Volume kostenlos. Unterschied: Short Interest
= offene Positionen (bi-wöchentlich), Short Volume
= tägliches Leerverkaufsvolumen.
Hohes Short-Volume + Earnings Beat = Short Squeeze
Kandidat (klassisches Setup).

**Was konkret:**
FINRA Reg SHO Daily Short Sale Volume:
  https://www.finra.org/sites/default/files/ftp/
  short-sale-volume-{YYYYMMDD}.txt

Daily Short Volume Ratio = Short Volume / Total Volume
Wenn > 50% → erhöhter Short-Druck.
Integrieren in: Research-Scoring + Torpedo-Monitor.

**Technisch:**
HTTP GET auf FINRA-URL (kostenlos, kein API-Key).
CSV parsen. Daily cronjob via n8n.
Supabase-Tabelle: short_volume_daily (ticker, date, ratio).
Bereits vorhandenes Short Interest ergänzen.

**Aufwand:** ~3h | **Modell:** SWE-1.5

---

## 🟠 ARCHITEKTUR: News-Pipeline Stufe 2 — Groq statt DeepSeek Chat

**Warum (korrigierte Einschätzung):**
FinBERT und generative LLMs lösen VERSCHIEDENE Aufgaben:
  FinBERT: Sentiment-Klassifizierung (bullish/bearish)
  LLM:     Text-Generierung, Strukturierung, Extraktion

DeepSeek Chat macht in news_processor.py die
Bullet-Point-Extraktion (Stufe 3 der Pipeline).
Aktuell limitiert auf 5 Calls/Ticker/Stunde (Kostenbremse).
Diese Bremse verhindert vollständige News-Abdeckung.

Groq (Llama 3 / Qwen) ist für diese Aufgabe besser:
  - Kostenloses Tier mit großzügigen Limits
  - 10-50× schneller als DeepSeek Chat
  - Kein Rate-Limit-Problem mehr
  - Strukturiertes JSON funktioniert zuverlässig

**Optimale Pipeline nach Migration:**
  Stufe 1: FinBERT lokal      → Noise-Filter (0 Kosten)
  Stufe 2: Groq/Llama3        → Bullet-Points + Entity
                                 Extraction (Groq free tier)
  Stufe 3: DeepSeek Chat      → Nur komplexe Analyse
                                 (signifikant weniger Calls)
  Stufe 4: Kimi K2.5          → Earnings-Transkripte
  Stufe 5: DeepSeek Reasoner  → Audit-Reports

**Entity Extraction (neu):**
"Betrifft diese News wirklich {ticker} oder wird der
Ticker nur erwähnt?" — Groq löst das in <100ms.
Verhindert False Positives (Apple in Nebensatz).

**Technisch:**
  pip install groq (minimal, kein komplexes Setup)
  Groq API Key: kostenlos registrieren
  news_processor.py: call_deepseek() →  call_groq()
  Kostenbremse (_DEEPSEEK_CALLS Limit) entfernen

**Cohere Command R:**
  Für RAG auf Earnings-Call-Transkripten evaluieren.
  Alternative zu Kimi K2.5 wenn Transkript-Analyse kommt.

**Aufwand:** ~2h | **Modell:** SWE-1.5

---

## NOTIZ: KI-Modell-Erweiterungen

Folgende Modelle wurden als potenzielle Ergänzungen
evaluiert:

  Groq + Llama 3 / Qwen: Hohe Inferenzgeschwindigkeit
  für News-Parsing. JETZT PRIORITÄRT für Bullet-Point-
  Extraktion in News-Pipeline Stufe 2.

  Cohere Command R: Stark für RAG auf Earnings-Calls.
  Interessant wenn Transkript-Analyse implementiert wird.
  Dann als Alternative zu Kimi K2.5 evaluieren.

  Groq API: Kostenloser Tier mit großzügigen Limits.
  Als Fallback wenn DeepSeek Rate-Limits erreicht.
  BYOK in Windsurf möglich.

Entscheidung: Groq wird für News-Parsing implementiert.
DeepSeek bleibt für komplexe Analyse und Audit-Reports.
Kein vorzeitiger Architektur-Wechsel.

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

*Zuletzt aktualisiert: 22. März 2026*
*Nächste Review: vor dem nächsten Major Feature*
