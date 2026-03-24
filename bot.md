# Kafin Trading Bot

## Zweck

Der Kafin-Trading-Bot ist ein datengetriebenes Research- und Entscheidungs-System für Aktien-Ticker.
Er sammelt strukturierte Markt-, Fundament-, Sentiment- und Ereignisdaten, verdichtet sie zu zwei Kern-Scores
(`Opportunity` und `Torpedo`) und erzeugt daraus eine begründete Handels- oder Review-Entscheidung.

Wichtig:

- Der Bot arbeitet **nicht** direkt gegen Supabase als Live-Backend.
- `get_supabase_client()` ist im Codebase ein **Kompatibilitäts-Shim** auf die lokale PostgreSQL-Container-DB.
- Entscheidungen sollen immer mit nachvollziehbarer Begründung, Top-Treibern, Hauptrisiken und Snapshot-Traceability entstehen.

## Kernprinzipien

- **Daten vor Meinung**
  - Entscheidungen sollen aus Daten entstehen, nicht aus Bauchgefühl.

- **Mehrquellen-Ansatz**
  - Fundamentaldaten, Earnings-Historie, technische Daten, Makro, Optionen, Insider, Short Interest, News, Reddit, Fear & Greed, Web-Intelligence und historische Signale werden zusammengeführt.

- **Explainability first**
  - Der Bot liefert nicht nur `buy`/`hold`, sondern auch die wichtigsten Gründe und Risiken.
  - Die Review-Entscheidung enthält Top-Driver, Top-Risks und einen maschinenlesbaren Reasoner-Output.

- **Manuelle Kontrolle vor Auto-Execution**
  - Der Review-Flow erzeugt eine Entscheidungsgrundlage.
  - Die eigentliche Ausführung bleibt bewusst getrennt und kann manuell erfolgen.

- **Speicher-Hygiene**
  - Alle gespeicherten Analysen und Entscheidungen können über Cleanup-Endpunkte entfernt werden.
  - Watchlist-Entfernen bietet optionales Massen-Cleanup aller zugehörigen Daten.

- **Automatisierte Datensammlung**
  - N8N Workflows sammeln automatisch News, SEC-Filings und andere Daten.
  - Kontinuierliche Datenversorgung für aktuelle Marktinformationen.
  - Health Monitoring确保 Workflow-Funktionalität.

- **Lokale Datenhaltung**
  - Persistenz läuft über die Container-PostgreSQL-DB.
  - Legacy-Supabase-Pfade bleiben nur als Abwärtskompatibilität erhalten.

## Aktueller Validierungsstand

- Backend-Test-Suite: `24 passed, 6 warnings` (keine Errors)
- Audit-/Review-Flow: läuft stabil und nutzt alle relevanten Datenquellen für die Bewertung; der Schwerpunkt liegt aktuell auf dem Sammeln von Audits und Decision Snapshots als Baseline für die spätere Kalibrierung
- Lernmodus: Gewichtungen werden noch **nicht** aggressiv angepasst, sondern erst nach ausreichender Audit-Historie empirisch nachgeschärft
- Profil-Fallback: Wenn FMP für einen validen Ticker kein Profil liefert, ergänzt der Bot die Bewertung jetzt über yfinance-Fundamentals statt den Ticker fälschlich als ungültig abzulehnen.
- Ticker-Resolver: Der Preis-/Daten-Check für bekannte Mappings und Suffix-Kandidaten ist korrigiert, sodass Resolver-Fehler nicht mehr falsche Negativentscheidungen triggern.
- News-Pipeline: Alerts, Bullet-Extraktion und Sentiment-Filter sind wieder konsistent
- Technische Restprobleme: Async-Fehler, Pydantic-Deprecation und UTC-Zeitstempel vollständig behoben
- Dokumentationsquelle: `bot.md` ist die kanonische Referenz und sollte bei Bot-Änderungen mitgezogen werden

## Architekturübersicht

### 1) Datensammlung

Die Daten kommen aus mehreren Schichten:

- **Fundamentals / Valuation**
  - `backend/app/data/fmp.py`
  - `backend/app/data/yfinance_data.py`
  - Liefert u. a. `pe_ratio`, `ps_ratio`, `market_cap`, `debt_to_equity`, `current_ratio`, `free_cash_flow_yield`, `beta`.

- **Earnings / Estimates / History**
  - `get_analyst_estimates()`
  - `get_earnings_history()`
  - Berücksichtigt Consensus, Beats/Misses, Surprise-% und Countdown bis Earnings.

- **Technicals**
  - `backend/app/analysis/chart_analyst.py`
  - `backend/app/data/yfinance_data.py`
  - Enthält z. B. `trend`, `rsi_14`, `support_level`, `resistance_level`, SMA-Abstände, ATR, Preisniveau.

- **Short Interest / Squeeze / FINRA**
  - Short-Interest-Daten werden aus den Datenquellen zusammengeführt.
  - `calculate_opportunity_score()` und `calculate_torpedo_score()` verwenden diese Signale mit Default-Fallbacks.

- **Insider Activity**
  - Kauf-/Verkaufsmuster, Cluster-Käufe/-Verkäufe, Bewertungsregeln.

- **Options**
  - Put/Call-Ratio, implied volatility, historical volatility, expected move, max pain, squeeze-nahe Signale.

- **Macro / Regime**
  - `backend/app/data/fred.py`
  - `backend/app/data/fear_greed.py`
  - `backend/app/data/market_overview.py`
  - VIX, Regime (`risk on`, `risk off`), Credit Spreads, Fear & Greed.

- **Sentiment / News / Social**
  - `backend/app/data/news_processor.py`
  - `backend/app/data/reddit_monitor.py`
  - `backend/app/data/web_search.py`
  - FinBERT/Web-Sentiment/Composite-Sentiment, Reddit-Mentions, Web-Intelligence, Divergenzen.

- **Langzeit- und Kurzzeitgedächtnis**
  - `backend/app/memory/short_term.py`
  - `backend/app/memory/long_term.py`
  - Kurzzeit-News-Bullets und Long-Term-Insights werden in die Entscheidung einbezogen.

### 2) Scoring

Die zentrale Logik liegt in:

- `backend/app/analysis/scoring.py`

Dort werden zwei Hauptwerte berechnet:

- **Opportunity Score**
  - misst bullische Chance / Qualität / Setup-Stärke.

- **Torpedo Score**
  - misst Abwärtsrisiko, Überbewertung, bärische Makro- oder Sentimentsignale.

#### Opportunity Score berücksichtigt u. a.

- Earnings Momentum
- Whisper Delta
- Valuation Regime
- Guidance Trend
- Technical Setup
- Sector Regime
- Short Squeeze Potential
- Insider Activity
- Options Flow

#### Torpedo Score berücksichtigt u. a.

- Valuation Downside
- Expectation Gap
- Insider Selling
- Guidance Deceleration
- Leadership Instability
- Technical Downtrend
- Macro Headwind

#### Decision Matrix

`get_recommendation()` übersetzt die Scores in eine finale Empfehlung:

- `strong_buy`
- `buy_hedge`
- `hold`
- `watch`
- `ignore`
- `strong_short`
- `potential_short`

Zusätzlich gibt es ein **Makro-Regime-Gate**:

- Risk-Off-Umfeld kann bullische Empfehlungen herunterstufen.
- Hoher VIX kann eine Absicherung erzwingen.

## Entscheidungs- und Review-Flow

### Audit-/Research-Report

- Route: `POST /api/reports/generate/{ticker}`
- Implementierung: `generate_audit_report()`

Der Audit-Report baut einen großen Kontext auf und speist ihn in den Reasoner:

- Company profile
- Valuation / Fundamentals
- Earnings history
- Technicals
- Short interest
- Insider data
- Options data
- Macro data
- Reddit sentiment
- Fear & Greed
- Web intelligence
- News bullet points
- Long-term memory
- Opportunity/Torpedo scores
- Top drivers / top risks
- Contrarian helper metrics

Der Report wird gespeichert und kann für spätere Analyse oder Vergleiche genutzt werden.

### Trade Review Decision

- Route: `POST /api/reports/review-trade/{ticker}`
- Implementierung: `generate_trade_review_decision()`

Dieser Pfad ist der wichtigste für den manuellen Handels-Review.
Er sammelt nicht nur die Basisdaten, sondern erzeugt zusätzlich:

- `prompt_payload`
- `top_drivers`
- `top_risks`
- `raw_data`
- `decision_text`
- `execution_note`
- `confidence`

Der Reasoner bekommt ein strikt definiertes JSON-Schema und soll eine konservative, datenbasierte Entscheidung zurückgeben.

### Snapshot / Learning / Nachvollziehbarkeit

Nach der Entscheidung wird ein Snapshot in `decision_snapshots` gespeichert.
Das ist wichtig für:

- spätere Performance-Analyse
- Lernkurve / Verbesserung der Entscheidungslogik
- Reproduzierbarkeit
- Debugging einzelner Entscheidungen

Snapshot-Daten enthalten u. a.:

- Scores
- Empfehlung
- Prompt
- Reasoner-Output
- Rohdaten-Kontext
- Preis-/RSI-/IV-Position zum Entscheidungszeitpunkt
- Earnings-Countdown
- Top Drivers / Top Risks

Aktuell ist das der zentrale Baseline-Mechanismus: Audits und Snapshots werden gesammelt, bevor Gewichtungen oder Schwellen aktiv kalibriert werden.

## Welche Daten der Bot für eine Bewertung nutzt

Die Entscheidung soll auf möglichst vielen erhobenen Signalen beruhen.
Die Review-/Audit-Kontexte enthalten aktuell u. a.:

- `earnings_history`
- `valuation`
- `short_interest`
- `insider_activity`
- `macro`
- `technicals`
- `news_memory`
- `news_list`
- `options`
- `social`
- `composite_sentiment`
- `web_sentiment_score`
- `finbert_sentiment`
- `sentiment_divergence`
- `analyst_grades`
- `sector_ranking`
- `ticker_sector`
- `reddit_sentiment`
- `reddit_mentions`
- `reddit_label`
- `fear_greed_score`
- `fear_greed_label`
- `chart_analysis`
- `relative_strength`
- `expected_move`
- `price_change_30d`
- `price_at_decision`
- `rsi_at_decision`
- `iv_atm_at_decision`
- `macro_regime`
- `vix`
- `credit_spread_bps`
- `earnings_date`
- `earnings_countdown`

## Begründung und Lernkurve

Der Bot soll nicht nur entscheiden, **was** er tut, sondern auch **warum**.

Das passiert über:

- **Top Driver / Top Risk Ranking**
  - zeigt die stärksten bullischen und bärischen Faktoren.

- **Reasoner-Prompt**
  - enthält die aggregierten Daten und verlangt eine knappe, begründete JSON-Antwort.

- **Decision Snapshot**
  - speichert den Kontext der Entscheidung für spätere Auswertung.

- **Score-History**
  - speichert Opportunity/Torpedo pro Tag.
  - dient dazu, Veränderungen über die Zeit sichtbar zu machen.

- **Performance-Tracking**
  - erlaubt zu messen, ob die Logik im Zeitverlauf besser wird.

Wenn du das System weiter verbesserst, solltest du immer fragen:

- Welche Signalgruppe hat die Entscheidung dominiert?
- Welche Daten waren fehlend und wurden neutral gefallbackt?
- War das Makro-Regime ein Gate?
- Wurden News und Social-Sentiment gegen Fundamentals abgewogen?
- Ist der aktuelle Call konsistent mit der früheren Lernhistorie?

## Datenbank / Persistenz

### Wichtige Tatsache

`get_supabase_client()` ist **kein echtes Supabase-Live-Backend** mehr.
Es ist ein Kompatibilitäts-Shim auf die lokale PostgreSQL-Container-DB.

### Relevante Komponenten

- `backend/app/db.py`
- `backend/app/database.py`
- `backend/app/init_db.py`

### Wichtige Tabellen / Datensätze

- `decision_snapshots`
- `audit_reports`
- `score_history`
- `daily_snapshots`
- `performance_tracking`
- `shadow_trades`

## News- und Signalverarbeitung

### News-Pipeline

- Datei: `backend/app/data/news_processor.py`

Die Pipeline:

1. Holt News
2. Filtert Duplikate
3. berechnet Sentiment
4. prüft Relevanz / Keywords
5. erkennt Torpedo-News
6. extrahiert Bullet Points
7. speichert Bullet Points
8. sendet Alerts bei kritischen Nachrichten

### Wichtige Regeln

- Stark negative News können einen Alert auslösen.
- Relevante News werden nicht nur über Sentiment, sondern auch über Keywords erkannt.
- Der Pipeline-Output ist ein wichtiger Input für Kurzzeit-Gedächtnis und Audit-Kontext.

## Frontend-Integration

### Research / Review UI

- `frontend/src/app/research/[ticker]/page.tsx`
- Button „Trade prüfen“ löst den Review-Flow aus.
- Ergebnis wird in einem Review-Modal angezeigt.
- Manual Trade Execution ist vom Review getrennt.

### API Client

- `frontend/src/lib/api.ts`
- Calls:
  - `reviewTrade(ticker)`
  - `manualTrade(...)`

## Mock-/Test-Strategie

Für Tests und lokale Entwicklung ist Mock-Verhalten bewusst vorgesehen.

### Wichtige Schalter

- `settings.use_mock_data = True`

### Test-Schwerpunkte

- Import-Stabilität
- Async-Funktionalität
- Mock-kompatible Rückgabeformen
- Backward-Compatibility für alte Feldnamen
- Report-Generierung ohne Live-Fehler

### Wichtige Testdateien

- `backend/tests/test_news_pipeline.py`
- `backend/tests/test_report_generator.py`
- `backend/tests/test_scoring.py`

## Best Practices für Änderungen am Bot

Wenn du den Bot weiterentwickelst, halte dich an diese Reihenfolge:

1. **Datenquelle prüfen**
   - Ist das Signal vorhanden?
   - Ist es Mock-/Live-kompatibel?

2. **Schema prüfen**
   - Passt das Feldformat zu `dict` und Pydantic-Objekten?

3. **Scoring prüfen**
   - Gibt es Default-Werte für fehlende Daten?
   - Kann ein `None` den Score crashen?

4. **Decision-Output prüfen**
   - Ist die Begründung klar?
   - Sind Top-Drivers und Top-Risks vollständig?

5. **Snapshot prüfen**
   - Wird der Entscheidungs-Kontext gespeichert?
   - Ist die Reproduktion später möglich?

6. **Tests prüfen**
   - Wurde die bestehende Test-Suite nicht gebrochen?

## Bekannte Hinweise

- Externe Datenquellen können während normaler Ausführung Netzwerkanfragen auslösen.
- Manche Teile des Codes erzeugen Deprecation-Warnings, sind aber funktional.
- Die Bot-Logik ist bewusst konservativ, wenn Daten fehlen.
- Fehlende Daten sollen in der Regel **neutral** und nicht crashend behandelt werden.

## Relevante Dateien

- `backend/app/analysis/report_generator.py`
- `backend/app/analysis/scoring.py`
- `backend/app/analysis/deepseek.py`
- `backend/app/data/news_processor.py`
- `backend/app/data/fmp.py`
- `backend/app/data/fred.py`
- `backend/app/data/reddit_monitor.py`
- `backend/app/data/web_search.py`
- `backend/app/memory/short_term.py`
- `backend/app/memory/long_term.py`
- `backend/app/db.py`
- `backend/app/database.py`
- `backend/app/routers/reports.py`
- `backend/app/routers/shadow.py`
- `frontend/src/app/research/[ticker]/page.tsx`
- `frontend/src/lib/api.ts`

## Kurzfassung

Der Bot ist ein **multi-signal Research- und Review-System** mit lokaler DB-Persistenz, Explainability und Snapshot-Traceability.
Die Entscheidungslogik basiert auf Score-Aggregation plus Reasoner-gestützter Begründung.
Wenn du ihn erweiterst, solltest du immer sicherstellen, dass neue Daten:

- im Kontext landen,
- im Score berücksichtigt werden,
- im Snapshot gespeichert werden,
- und in der Begründung sichtbar bleiben.
