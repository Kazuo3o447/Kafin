# KAFIN — Zukunftsvisionen & Technical Debt

*Erstellt: 21. März 2026*
*Prinzip: Trading-First statt Data-First*

---

## ✅ FEATURE: Modular Backend Architecture (v6.1.5)

**Status: ✅ ERLEDIGT — v6.1.5 (22.03.2026)**

- ✅ Monolithische `main.py` vollständig in fachliche Router zerlegt
- ✅ Neue Router-Struktur unter `backend/app/routers/` (data, news, reports, watchlist, analysis, shadow, logs, system, web_intelligence)
- ✅ Admin-Endpunkte in `backend/app/admin/` zentralisiert
- ✅ Startup/Shutdown-Logik in `main.py` modernisiert und entschlackt
- ✅ API-Keys und Settings-Management im Admin-Panel verifiziert

---

## ✅ FEATURE: Prompt Quality + Modell-Optimierung

**Status: ✅ ERLEDIGT — v6.1.4 (22.03.2026)**

- ✅ Prompts v0.4: Alle TODO-Platzhalter implementiert
- ✅ audit_report: Max Pain, PCR-OI, Squeeze-Signal, CEO, Mitarbeiter, Peers
- ✅ post_earnings: AH-Reaktion, Expected Move, Fear & Greed
- ✅ morning_briefing: Fear & Greed Score/Label
- ✅ DeepSeek Modell-Matrix: Reasoner (Audit/Torpedo), Chat (schnelle Tasks)
- ✅ groq.py: API-Key aus settings statt module-level env
- ✅ TODO-Kommentare aus allen Prompts entfernt

---

## ✅ FEATURE: API Usage Tracking + Token Counter

**Status: ✅ ERLEDIGT — v6.1.3 (22.03.2026)**

- ✅ usage_tracker.py: Redis-Puffer + async DB-Flush (5min)
- ✅ DeepSeek: input/output Tokens + Kosten ($/Call) pro Modell
- ✅ Groq: input/output Tokens (Free Tier = $0.00)
- ✅ FMP: Call-Counter vs. 250/Tag Limit
- ✅ Finnhub: Call-Counter vs. 60/min Limit
- ✅ GET /api/admin/api-usage: Aggregierte Summary
- ✅ Settings → APIs: ApiUsageBlock mit Balken + Token-Tabelle

---

## ✅ FEATURE: Supabase → PostgreSQL Migration

**Status: ✅ ERLEDIGT — v6.0.4 (K6-1 bis K6-4 abgeschlossen)**

- ✅ PostgreSQL 16 + pgvector läuft lokal als Docker-Container
- ✅ Drop-in Adapter mit Supabase-kompatibler API
- ✅ Auto-Embedding Pipeline mit all-MiniLM-L6-v2
- ✅ RAG Query Endpoints für semantische Suche
- ✅ Vollständige Migration abgeschlossen, Supabase abgelöst

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

### ✅ DeepSeek Prompts v0.3 Update
**Status: ✅ ERLEDIGT (22.03.2026) — v5.14.3**
- news_extraction v0.3: Entity-Relevanz-Check mit is_directly_relevant + relevance_reason
- audit_report v0.3: Max Pain, PCR-OI, Squeeze-Signal, Firmenprofil (CEO, Peers)
- post_earnings v0.3: AH-Reaktion, Expected Move, Fear & Greed im Kontext
- morning_briefing v0.3: Fear & Greed bei Extremen (≤25 oder ≥75)
- chart_analyst: Optionale Pre-Market Parameter für Pre-Market Preise
- Alle neuen Features sind in Prompts vorbereitet mit TODO-Kommentaten für fehlende Backend-Implementierungen

---

## 🟠 FEATURE: Reddit Retail vs. Smart Money Divergenz

**Warum (Edge):**
Insider (SEC Form 4) = Smart Money.
Reddit WSB/stocks = Retail-Sentiment.
Divergenz = Contrarian-Signal:
  Retail extrem gierig + Insider verkaufen massiv
  → Torpedo-Setup (Short/Put-Kandidat)
  Retail panik-verkauft + Insider kaufen
  → Opportunity-Setup (antizyklisch Long)

Das ist kein Sentiment-Indicator — es ist ein
Divergenz-Detector. Sentiment allein ist wertlos.

**Was konkret:**
Reddit JSON-Endpoints (kein API-Key):
  https://www.reddit.com/r/wallstreetbets/search.json
    ?q={ticker}&sort=new&limit=25&t=day
  https://www.reddit.com/r/stocks/search.json
    ?q={ticker}&sort=new&limit=25&t=day

FinBERT läuft bereits lokal → Titel-Analyse kostenlos.
Insider-Ratio: bereits aus Finnhub/EDGAR.

Neuer Score: "retail_smart_divergence"
  +1.0 = Retail bullisch & Insider kaufen (Bestätigung)
  -1.0 = Retail bullisch & Insider verkaufen (Torpedo)
   0.0 = kein klares Signal

Anzeige: Research Dashboard SentimentBlock,
Torpedo-Score "leadership_instability" ergänzen.
Telegram-Alert wenn Divergenz > 0.7.

**Wo integrieren:**
  sentiment_monitor.py erweitern oder neues
  reddit_monitor.py
  scoring.py: retail_smart_divergence als
  optionaler Torpedo-Faktor

**Aufwand:** ~3h | **Modell:** SWE-1.5
**Priorität:** Batch 2

---

## 🔴 FEATURE: Sympathy Play Radar

**Warum (Edge):**
IV-Crush nach Earnings macht direkte Earnings-Trades
teuer. Profis handeln den Peer: wenn ASML fällt aber
TSM sich hält → TSM zeigt relative Stärke.
Bekannter Edge: Sympathy Run (Peer steigt mit)
oder Divergenz (Peer hält sich → kaufen).

**Was konkret:**
peer_monitor.py erkennt bereits wenn ein Peer meldet.
Aber: keine Reaktions-Analyse NACH der Meldung.

Erweitern: calculate_peer_reaction() ausbauen.
Wenn Ticker X Earnings meldet und sich ±Y% bewegt:
  1. Lade Top 3 Peers (aus cross_signals in Watchlist)
  2. Hole deren Kursreaktion (yfinance, prepost=True)
  3. Klassifiziere:
     "sympathy_run": Peer bewegt sich gleich
     "relative_strength": Ticker fällt, Peer stabil/steigt
     "divergence": Ticker steigt, Peer fällt

Anzeige: Earnings Battle Card + Research Dashboard
  "NVDA meldet -5% → ASML zeigt relative Stärke (+0.3%)"

Telegram-Alert:
  "🔗 SYMPATHY: ASML -5% nach Earnings.
   NVDA hält sich (+0.2%) → Relative Stärke.
   IV bei NVDA jetzt günstig."

**Technisch:**
peer_monitor.py: nach check_peer_earnings_today()
neue Funktion check_sympathy_reaction() hinzufügen.
n8n: nach Earnings-Scan triggern.

**Aufwand:** ~3h | **Modell:** SWE-1.5
**Priorität:** Batch 2
**Status: ✅ ERLEDIGT (22.03.2026) — v5.16.1**

---

## 🟠 FEATURE: GEX Proxy (Gamma Exposure)

**Warum (Edge):**
Market Maker müssen Optionsverkäufe hedgen.
Positives GEX = Kurs ist "sticky" (MM kaufen bei
Rückgängen, verkaufen bei Anstiegen → mean reversion).
Negatives GEX = Kurs ist "explosiv" (MM verstärken
Bewegungen → Gamma Squeeze möglich).

Das erklärt warum manche Aktien sich kaum bewegen
und andere in kurzer Zeit 10% machen.

**Was konkret:**
yfinance option_chain() — bereits implementiert für
Max Pain (Batch 1). Erweiterung:

GEX-Formel pro Strike:
  gamma = option.gamma (yfinance liefert das)
  gex_strike = gamma * openInterest * 100 * price
  total_gex = sum(call_gex) - sum(put_gex)

Interpretation:
  total_gex > 0: sticky (MM dämpfen Bewegung)
  total_gex < 0: explosiv (MM verstärken Bewegung)
  total_gex nahe 0: Flip-Zone (gefährlich)

Anzeige: Research Dashboard, Options-Block:
  "GEX: +2.3M (sticky) — Kurs zwischen $140-$155
   magnetisch. Ausbruch braucht Volumen."

**Technisch:**
Erweiterung von get_options_oi_analysis() in
yfinance_data.py. gamma aus option_chain verfügbar.

**⛔ TECHNISCHE EINSCHRÄNKUNG (verifiziert):**
yfinance option_chain() gibt KEIN Gamma zurück.
Spalten: strike, bid, ask, volume, openInterest,
impliedVolatility — kein delta/gamma/theta.

GEX erfordert entweder:
  - Polygon.io Options API ($29/Monat)
  - Tradier Options API (kostenlos bis 10K calls/Tag)
  - CBOE Livevol (teuer, institutional)

Empfehlung: Tradier API evaluieren.
  https://developer.tradier.com/documentation/markets/get-chains

Bis API vorhanden: als OFFEN markieren.
Status bleibt ⛔ BLOCKIERT (API-Key nötig).

**Aufwand:** ~2h | **Modell:** SWE-1.5
**Priorität:** Batch 2 (nach Max Pain live)

---

## 🟠 FEATURE: 10-Q Filing RAG (Tonalitäts-Diff)

**Status: ✅ ERLEDIGT — v6.2.2 (23.03.2026)**

**Warum (Edge):**
In einem 50-seitigen 10-Q verstecken sich die
wichtigsten Signale in veränderten Formulierungen.
"We expect margins to remain stable" → "We anticipate
continued margin pressure" ist ein massives Signal.
Institutionelle Analysten suchen genau das — manuell.
Kafin macht das automatisch.

**Modell-Auswahl:**
Google Gemini Flash: kostenloser Tier,
1M Token Kontext, ideal für zwei 10-Qs gleichzeitig.
Claude Haiku: Alternative, günstiger Tier.
Kimi K2.5: bereits integriert, 256K Kontext.

**Was konkret:**
  1. SEC EDGAR: letztes + vorletztes 10-Q laden
     (bereits EDGAR-Integration vorhanden)
  2. Text extrahieren (pdfplumber oder html parser)
  3. Gemini Flash Prompt:
     "Vergleiche diese Dokumente. Nenne die 3
      Absätze wo Management die Tonalität bezüglich
      Kosten, Margen oder Wachstum verändert hat.
      Format: [ABSCHNITT] VORHER vs. NACHHER"
  4. Output in Research Dashboard: "10-Q Diff" Block

Alert: wenn negativer Tonalitätswechsel erkannt →
Torpedo-Signal.

**Technisch:**
Neues Modul: backend/app/analysis/filing_rag.py
Neuer Endpoint: GET /api/data/filing-diff/{ticker}
Gemini API Key: kostenlos registrieren.
Cache: 24h (10-Qs ändern sich nicht).

**Implementiert:**
- ✅ gemini.py: Gemini 1.5 Flash Client
- ✅ filing_rag.py: SEC EDGAR → Gemini Pipeline
- ✅ GET /api/data/filing-diff/{ticker} Endpoint
- ✅ Research: FilingDiffBlock on-demand
- ✅ 5 Kategorien: Margen, Wachstum, Risiken, Guidance, Liquidität
- ✅ Gesamt-Signal: BULLISH/BEARISH/GEMISCHT/NEUTRAL

**Aufwand:** ~4h | **Modell:** Sonnet / SWE-1.5
**Priorität:** Batch 3

---

## 🟠 FEATURE: Shadow Trading Journal mit KI-Lernschleife

**Warum (Edge):**
Du triffst die Entscheidungen — aber dein eigener
Bias ist das größte Risiko. Das System soll dich
nicht ersetzen sondern optimieren.

Aktueller Stand: shadow_portfolio.py öffnet/schließt
Trades automatisch aus Audit-Reports. Kein manueller
Trade-Grund. Keine Performance-Analyse nach Kategorie.

**Was konkret:**

Phase A — Trade-Journal (manuell):
  Performance-Seite: "Trade eröffnen" Button
  Pflichtfelder:
    Ticker, Richtung (Long/Short/Put/Call)
    Hauptgrund (Dropdown):
      "IV Mismatch" | "Sentiment Divergenz" |
      "Relative Stärke" | "Sympathy Play" |
      "Earnings Beat erwartet" | "Torpedo erkannt" |
      "Technisches Breakout" | "Contrarian Setup"
    Notiz (optional)
  Shadow-Trade wird mit trade_reason gespeichert.

Phase B — Wöchentliche KI-Analyse (Sonntags-Report):
  DeepSeek analysiert alle abgeschlossenen Trades
  der letzten 30 Tage nach trade_reason:
  "Deine Contrarian-Setups: 4/5 profitabel (80%).
   Deine Technischen Breakouts: 2/6 profitabel (33%).
   Empfehlung: Fokus auf Contrarian, weniger Breakouts."

**Technisch:**
shadow_portfolio.py: trade_reason Feld ergänzen.
DB: shadow_trades Tabelle + trade_reason Spalte.
Frontend: performance/page.tsx Button + Modal.
Sunday Report: performance_analysis() Funktion.

**Aufwand:** Phase A ~3h, Phase B ~3h
**Modell:** SWE-1.5 (Phase A), SWE-1.5 (Phase B)
**Priorität:** Phase A Batch 3, Phase B Batch 4
**Status: ✅ ERLEDIGT (22.03.2026) — v5.16.2 (Phase A)**

---

## �🟠 FEATURE: Max Pain Kalkulation

**Status: ✅ ERLEDIGT (22.03.2026) — v5.13.0**

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

**Status: ✅ ERLEDIGT (22.03.2026) — v5.13.0**

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

**Status: ✅ ERLEDIGT (22.03.2026) — v5.13.6**

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

## ✅ MARKETS: Marktbreite 5T/20T Verlauf
**Status: ✅ ERLEDIGT (22.03.2026) — v5.15.0**

Tägliche Breadth-Werte werden in `daily_snapshots` gespeichert.
Historische 5T/20T-Werte werden aus Supabase geladen.
`pct_above_sma50_5d_ago`, `pct_above_sma50_20d_ago` und `breadth_trend_5d`
sind jetzt im Markets-Dashboard sichtbar.

## ✅ GENERAL NEWS ENDPOINT
**Status: ✅ ERLEDIGT (22.03.2026) — v6.1.5**

**Was:** GET /api/news/general für marktweite Nachrichten.

**Implementiert:**
- `GET /api/news/general` im `news_router`
- Nutzt `get_market_news_for_sentiment()` aus `market_overview.py`
- Integriert in die neue modulare Router-Struktur.

---

## 🟡 FUTURE: Marktbreite verbessern
Aktuell: 30 Dow-Titel als Proxy.
Besser: S&P 500 Advance-Decline-Linie via ^SPXAD (yfinance).
`yf.Ticker("^SPXAD").history(period="1mo")` — testen ob verfügbar.
Aufwand: 30 Minuten wenn ^SPXAD korrekt liefert.

## ✅ KASKADE 3 ABGESCHLOSSEN

- **Fear & Greed Score** → ✅ ERLEDIGT (22.03.2026) — v5.14.0 / v5.14.1
  - `backend/app/data/fear_greed.py` mit 5 Komponenten und 30min Cache
  - `GET /api/data/fear-greed`
  - `FearGreedBlock` direkt nach MacroDashboard auf `/markets`
- **Watchlist Auto-Update** → ✅ ERLEDIGT (22.03.2026) — v5.14.2
  - `post_earnings_review.py` aktualisiert `web_prio` + `notes` nach Earnings
  - Cache-Invalidierung für Watchlist / Research Dashboard / Earnings Radar
- **DeepSeek Prompts** → ✅ ERLEDIGT (22.03.2026) — v5.14.3
  - `news_extraction`: `is_directly_relevant` + `relevance_reason`
  - `audit_report`: Max Pain, PCR-OI, Squeeze-Signal, Firmenprofil
  - `post_earnings`: AH-Reaktion + Fear & Greed Kontext
  - `morning_briefing`: Fear & Greed bei Extremen

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

## ✅ CHART ANALYSIS COMPLETE OVERHAUL

**Status: ✅ ERLEDIGT (22.03.2026) — v6.1.6**

**Was:** Chart-Analyse mit immer sichtbaren Begründungen und ETF/Index-Unterstützung.
→ Kein Akkordeon-Klick mehr nötig, vollständige Audit-Integration, Asset-Type Detection.

**Implementiert:**
- **Frontend**: TradeSetupBlock zeigt why_entry/why_stop/trend_context/turnaround_conditions IMMER sichtbar
- **Backend**: Asset-Type Detection für ETF_TICKERS und INDEX_TICKERS Konstanten
- **API**: /research/{ticker} liefert is_etf, is_index, asset_type Felder
- **Frontend**: Badge im Research Header (ETF=blau, Index=lila)
- **Markets Page**: "Research" Button neben "⚡ Chart" für Indizes
- **Audit Integration**: report_generator.py chart_str enthält alle reasoning fields
- **Chart Analyst**: max_tokens 2048, explizite Anweisung für vollständige Sätze

**Aufwand:** ~4h, SWE-1.5.

---

## ✅ OPTIONEN OPEN INTEREST PRO STRIKE

**Status: ✅ ERLEDIGT (22.03.2026) — v5.15.2**

**Was:** Welche Strike-Preise haben das meiste Open Interest?
→ "Max Pain" Berechnung, magnetische Support/Resistance-Level.
Hohe OI-Strikes = Kurse tendieren zu diesen Leveln vor Expiration.

**Warum noch nicht:** yfinance liefert OI pro Strike bereits
(option_chain), aber die Visualisierung und Max-Pain-Berechnung
fehlen im Frontend.

**Implementierung wenn bereit:**
- Backend: Neuer Endpoint GET /api/data/options-oi/{ticker}
  → Gibt Top-10 Strikes nach OI zurück (Calls + Puts getrennt)
- Frontend: `OptionsOiBlock` im Research-Dashboard mit On-Demand-Button,
Call/Put-Heatmap, Max-Pain-Hervorhebung und ATM-Markierung.
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

## ✅ EARNINGS-KALENDER IM RESEARCH-DASHBOARD

**Status: ✅ ERLEDIGT (22.03.2026) — v5.15.3**

**Was:** Watchlist-Earnings der nächsten 14 Tage direkt im
Research-Dashboard anzeigen.
"HIMS meldet in 12 Tagen — und diese Peers auch bald..."

**Implementiert:** `sector_earnings_upcoming` im `EarningsContextBanner`
mit klickbaren Research-Links.

**Aufwand:** erledigt.

---

## ✅ INTRADAY — VWAP

**Status: ✅ ERLEDIGT (22.03.2026) — v5.15.1**

**Was:** Volume Weighted Average Price — Fair-Value-Linie für Daytrader.
Long über VWAP = bullish Intraday-Bias. Short darunter = bearish.

**Implementiert:**
- `GET /api/data/vwap/{ticker}`
- `get_vwap()` aus 5-Minuten-Yahoo-Intraday-Daten
- Cache: 2 Minuten während Marktstunden, 1 Stunde sonst
- Research Dashboard: VWAP-Badge mit Delta % und Marktstatus

---

## ✅ P2B EARNINGS-HISTORIE FALLBACK

**Status: ✅ ERLEDIGT (22.03.2026) — v5.15.3**

**Was:** Wenn FMP keine Earnings-Historie liefert,
nutzte das Research Dashboard `yfinance` als Fallback.

**Implementiert:**
- `get_earnings_history_yf()` in `backend/app/data/yfinance_data.py`
- FMP → yfinance Umschaltung im `api_research_dashboard`
- `SimpleNamespace` hält das erwartete History-Interface kompatibel

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
