# ANTIGRAVITY — Earnings Intelligence Platform
## Plattform-Spezifikation v2.0
### Stand: 7. März 2026

---

## 1. Vision

Ein persönliches Research-Team in Software. Die Plattform sammelt, filtert, kontextualisiert und bewertet — der Trader entscheidet. Sie ersetzt nicht das Denken, sondern eliminiert die manuelle Recherche-Arbeit und liefert strukturierte Handlungsempfehlungen wie ein Analyst.

**Kernüberzeugungen, die in der Plattformlogik verankert sein müssen:**

Momentum und Narrative dominieren die Märkte seit ca. 2018 stärker als klassische Value-Metriken. Passive Flows (ETF-Sparpläne, Buybacks, 401k) erzeugen einen permanenten, preisunelastischen Kaufdruck, der Index-Shorts strukturell benachteiligt. Das "Bad News is Good News"-Paradox ist real: Schwache Wirtschaftsdaten führen zu Fed-Senkungserwartungen, was den Markt stützt. Solange die Fed senkt oder neutral bleibt, sind Makro-Shorts eine Sisyphos-Aufgabe.

Bewertung ist kein Timing-Signal. Sie ist ein Regime-kontextuelles Maß — gleichzeitig Opportunity (günstiger als das Regime rechtfertigt?) und Risiko (wie tief der Fall bei Narrative-Bruch?). Ein Unternehmen, das vom Markt als KI-Enabler statt als traditioneller Softwarehersteller eingeordnet wird, verdient ein höheres Multiple. Dasselbe Unternehmen bei einem Guidance-Miss verliert aber überproportional, weil das Premium-Regime nicht mehr gestützt wird (MongoDB-Effekt).

Torpedo-Vermeidung ist profitabler als Beat-Vorhersage. Ein einziger -25% Overnight-Gap eliminiert die Gewinne von fünf erfolgreichen Trades.

Wenn der Trader bärisch positioniert sein will, empfiehlt die Plattform niemals breite Index-Shorts, sondern chirurgische Instrumente: Sektor-ETF-Puts, Einzeltitel-Shorts, Pair-Trades.

---

## 2. Der wöchentliche Zyklus

### 2.1 Laufend (automatisch, 24/7)

News-Pipeline sammelt Nachrichten zu allen Watchlist-Titeln. Jede Nachricht durchläuft FinBERT (lokal). Nur relevante Nachrichten (Sentiment-Score > 0.3 oder < -0.3) werden weiterverarbeitet. DeepSeek extrahiert 3-5 Stichpunkte pro relevanter Nachricht. Stichpunkte landen im Kurzzeit-Gedächtnis (Supabase). Bei hoher Relevanz: Telegram-Push aufs Handy.

Parallel: SEC EDGAR RSS-Feed wird alle 10 Minuten via n8n gescannt. Form 8-K und Form 4 (Insider-Transaktionen) werden sofort verarbeitet. Bei Torpedo-Signalen (Schlüsselwörter wie "investigation", "subpoena", "restatement", Insider-Cluster-Verkauf) erfolgt ein sofortiger Alert.

Bitcoin: CoinGlass-Daten werden regelmäßig abgerufen. Bei extremen Funding Rates oder Annäherung an große Liquidationscluster: Telegram-Alert.

### 2.2 Sonntag (automatisch generiert, per E-Mail + Web)

**Teil 1 — Makro-Regime-Header**

Fünf bis sechs Zeilen, die das Gesamtbild setzen. Fed-Stance und Markterwartung für nächste Sitzung. Credit Spreads (FRED). VIX-Level mit Interpretation. Yield Curve Status. Geopolitisches Risiko-Level. Sektor-Rotation (wohin fließt Geld, woher fließt es ab).

Schließt mit einer klaren Aussage: "Index-Shorts: Nicht empfohlen" oder "Selektive Shorts möglich: [konkretes Instrument]". Bei bärischer Einschätzung werden präzise Instrument-Vorschläge gemacht — Sektor-ETF-Puts, Einzeltitel mit hohem Torpedo-Score, Pair-Trades. Niemals nur "Short Nasdaq".

**Teil 2 — Bitcoin-Lagebericht**

Kurs und 7-Tage-Trend. Liquiditätscluster oben und unten (CoinGlass Heatmap-Daten). Open Interest Trend und Niveau. Funding Rate mit Interpretation. Long/Short Ratio. Makro-Korrelation (DXY, Realzinsen, M2-Trend). Empfehlung (Long / Short / Abwarten) mit Begründung und Schlüssel-Levels.

**Teil 3 — Earnings-Kalender der Woche**

Übersicht: Welche Watchlist-Titel melden wann (Datum, Pre-Market oder After-Hours). Plus: Relevante Nicht-Watchlist-Titel aus dem Earnings-Radar mit Hinweis, für welchen Watchlist-Titel sie relevant sind.

**Teil 4 — Audit-Reports**

Pro meldendem Watchlist-Titel ein vollständiger Report (siehe Abschnitt 4).

### 2.3 Zwischen Sonntag und Earnings

**Torpedo-Warnsystem:** Überwacht den News-Feed auf Informationen, die eine bestehende Report-Empfehlung infrage stellen. Downgrades, Ermittlungen, Insider-Verkäufe, SEC-Filings, Management-Abgänge. Kein neuer Report — nur ein kurzer Telegram-Alert mit den neuen Stichpunkten und dem Hinweis, die Empfehlung zu überprüfen.

**Makro-Trigger-Alerts:** Bei materiellen Events zwischen zwei Sonntagen — Arbeitsmarktdaten, Fed-Entscheidung, Geopolitik-Eskalation, CPI-Überraschung. Kurze Einordnung: Was ist passiert? Was bedeutet es für das aktuelle Makro-Regime? Und konkret: Wie wirkt es sich auf offene Positionen aus?

### 2.4 Nach Earnings

Post-Earnings-Review wird automatisch generiert: Tatsächliches EPS und Revenue vs. Konsens und Whisper. Kursreaktion Tag 1 und Woche 1. Vergleich mit KI-Empfehlung — lag die Richtung richtig? Lag die Magnitude richtig? Welche Signale im Report waren prädiktiv, welche irreführend? Archivierung aller Daten ins Langzeit-Gedächtnis.

### 2.5 Quartalsweise

Aggregierte Auswertung: Trefferquote der Empfehlungen nach Score-Bereich (z.B. "Bei Opportunity ≥ 7 und Torpedo ≤ 3 lagen wir in 72% der Fälle richtig"). Welche Signal-Typen hatten die höchste Vorhersagekraft? Prompt-Optimierung basierend auf Erkenntnissen.

---

## 3. Duales Scoring-System

### 3.1 Opportunity-Score (1-10)

Bewertet die Attraktivität des Trades.

Earnings-Momentum hat ein Gewicht von 15%. Gemessen an historischen Surprises (letzte 8 Quartale), dem SUE-Trend (Standardized Unexpected Earnings), und ob das Unternehmen eine Serie von Beats oder Misses hat. Datenquelle: FMP Historical Earnings, Finnhub.

Whisper vs. Konsens Delta hat ein Gewicht von 15%. Wie weit liegt der Whisper über oder unter dem Konsens? Aktien, die den Konsens schlagen aber den Whisper verfehlen, fallen in 55% der Fälle. Datenquelle: Earnings Whispers (manuell oder API), Analystenschätzungen via FMP.

Bewertung im Regime-Kontext hat ein Gewicht von 15%. Nicht absolut "teuer oder günstig", sondern: Ist die Aktie günstiger als das aktuelle Bewertungs-Regime rechtfertigt? Findet ein Narrative-Shift statt, der ein höheres Regime erlaubt? (Beispiel: UTHR wird vom Pharma- zum Biotech-Plattform-Multiple re-rated). Datenquelle: FMP Fundamentals, Peer-Vergleich.

Forward Guidance Trend hat ein Gewicht von 15%. Beschleunigt oder verlangsamt sich die Kern-Wachstumsmetrik? (Bei MongoDB war es Atlas-Wachstum, bei NVIDIA wäre es Datacenter-Revenue). Wurde die Guidance in den letzten Quartalen angehoben, bestätigt oder gesenkt? Datenquelle: Langzeit-Gedächtnis, KI-Analyse des letzten Earnings-Calls.

Technisches Setup hat ein Gewicht von 10%. Trend (über/unter 50/200-Tage), RSI, Support/Resistance-Level, 52-Wochen-Hoch-Nähe. Datenquelle: Historische Kursdaten via yfinance oder FMP.

Sektor-Regime hat ein Gewicht von 10%. Relative Stärke des Sektors vs. S&P 500 auf 1-, 4- und 12-Wochen-Basis. Fließt Geld in oder aus dem Sektor? Haben Bellwether im selben Sektor bereits positiv gemeldet? Datenquelle: Sektor-ETF-Daten, Earnings-Radar.

Short-Squeeze-Potenzial hat ein Gewicht von 10%. Short Interest als Prozent des Floats (über 20% wird interessant), Days-to-Cover (über 5 Tage wird explosiv bei einem Beat), Trend der Short-Quote (steigend oder fallend). Datenquelle: Finnhub Short Interest, FINRA-Meldungen.

Insider-Aktivität hat ein Gewicht von 5%. Cluster-Käufe (mehrere Insider kaufen gleichzeitig) sind das stärkste bullische Signal. Besonders relevant bei kleineren Unternehmen. Datenquelle: SEC Form 4 via Finnhub oder FMP.

Options-Flow hat ein Gewicht von 5%. Ungewöhnliche Aktivität (Volumen über Open Interest), Block-Trades über $20.000 Prämie, IV-Niveau relativ zum historischen Schnitt. Datenquelle: Phase 6 (Unusual Whales / FlowAlgo), vorher vereinfachte IV-Daten.

### 3.2 Torpedo-Score (1-10)

Bewertet das Downside-Risiko.

Bewertung als Fallhöhe hat ein Gewicht von 20%. P/E und P/S relativ zu Peers UND zum eigenen 3-Jahres-Median. Je weiter über dem Schnitt, desto höher die Bar für eine positive Reaktion und desto brutaler der Fall bei Enttäuschung. MongoDB handelte beim 11,4x P/S vs. 2,1x Branchenschnitt — maximale Fallhöhe. Datenquelle: FMP Fundamentals.

Erwartungs-Gap hat ein Gewicht von 20%. Was ist im Aktienkurs eingepreist vs. was erwartet der Konsens? Wenn die Aktie in den 30 Tagen vor Earnings 15% gestiegen ist, erwartet der Markt einen massiven Beat. Ein normaler Beat reicht dann nicht. Umgekehrt: Wenn die Aktie 20% gefallen ist, sind schlechte Nachrichten teilweise eingepreist. Datenquelle: Kursperformance + Konsensschätzungen.

Insider-Selling hat ein Gewicht von 15%. Nicht nur ob, sondern wie viel relativ zur Position. Ein Director, der 11% seiner Anteile abstößt (wie bei MongoDB), ist radikal anders als ein CEO, der 0,5% für Steuern verkauft. Cluster-Verkäufe (mehrere Insider gleichzeitig) sind das stärkste Warnsignal. Datenquelle: SEC Form 4 via Finnhub oder FMP.

Guidance-Verlangsamung hat ein Gewicht von 15%. Flacht die Kern-Wachstumsmetrik Quartal über Quartal ab? Bei Premium-Bewertung ist ein abflachender Trend das gefährlichste Setup: Der Markt erwartet Beschleunigung, bekommt Verlangsamung. Datenquelle: Langzeit-Gedächtnis (historische Guidance + Kern-Metriken).

Leadership-Instabilität hat ein Gewicht von 10%. Neue CEOs, CFOs oder CROs in den letzten 6 Monaten? Abgänge im Management angekündigt? Neue CEOs setzen Erwartungen gern runter (konservative erste Guidance). Bei MongoDB war der CEO erst 4 Monate im Amt. Datenquelle: News-Gedächtnis.

Technischer Downtrend hat ein Gewicht von 10%. Aktie unter 200-Tage-Durchschnitt? RSI-Divergenz? Keine technische Unterstützung bei einem Selloff? Eine Aktie, die in einen Downtrend hinein Earnings meldet, hat keinen Puffer — MongoDB war YTD -21% vor den Earnings. Datenquelle: Historische Kursdaten.

Makro-Gegenwind hat ein Gewicht von 10%. Sektor-Regime negativ? VIX erhöht? Befindet sich der Markt in einem Umfeld, in dem gute Zahlen bestraft werden? Datenquelle: Makro-Header.

### 3.3 Entscheidungsmatrix

Opportunity ≥ 7, Torpedo ≤ 3: STRONG BUY — Aktie oder Call-Optionen.
Opportunity ≥ 7, Torpedo 4-6: BUY MIT ABSICHERUNG — Aktie plus Protective Put oder Bull Call Spread.
Opportunity ≥ 7, Torpedo ≥ 7: WATCH — Zu riskant trotz Opportunity. Nach Earnings re-evaluieren.
Opportunity 4-6, Torpedo ≤ 3: MODERATE BUY — Kleinere Position.
Opportunity 4-6, Torpedo 4-6: KEIN TRADE — Risk/Reward nicht überzeugend.
Opportunity 4-6, Torpedo ≥ 7: POTENTIELLER SHORT — Put-Optionen wenn Narrative bricht.
Opportunity ≤ 3, Torpedo ≥ 7: STRONG SHORT — Bear Put Spread.
Opportunity ≤ 3, Torpedo ≤ 3: IGNORIEREN — Kein Edge.

---

## 4. Audit-Report Struktur (Deutsch)

```
═══════════════════════════════════════════════════════
[TICKER] — [UNTERNEHMENSNAME]
Earnings: [Datum], [Pre-Market / After-Hours]
═══════════════════════════════════════════════════════

OPPORTUNITY-SCORE: [X/10]    TORPEDO-SCORE: [X/10]
EMPFEHLUNG: [Strong Buy / Buy / Hold / Short / Strong Short]

─── ZUSAMMENFASSUNG ───
[3-4 Sätze: Was ist die These? Warum diese Empfehlung?
Was ist das größte Risiko? Was ist der Katalysator?]

─── ERWARTUNGEN & WHISPER ───
EPS-Konsens: $X.XX | Whisper: $X.XX | Delta: X%
Umsatz-Konsens: $X.XXB | Whisper: $X.XXB
Letzter Beat/Miss: [Ergebnis + Kursreaktion]
Historisches Muster: [X von 8 Quartalen geschlagen, Ø Surprise X%]

─── BEWERTUNG IM REGIME-KONTEXT ───
Aktuelles P/E: Xx | Sektor-Median: Xx | Eigener 3J-Median: Xx
P/S: Xx | Peer-Vergleich: [günstig / fair / teuer]
Regime: [Wie ordnet der Markt das Unternehmen aktuell ein?]
Narrative-Shift: [Gibt es Anzeichen für Re-Rating? Wohin?]
Asymmetrie: [Upside bei Regime-Wechsel vs. Downside bei Bruch]

─── NACHRICHTEN-GEDÄCHTNIS ───
[Datum] — [Stichpunkt]
[Datum] — [Stichpunkt]
...
KI-Einordnung: [Wie beeinflussen die News die Earnings-Erwartung?]

─── TECHNISCHES SETUP ───
Trend: [Aufwärts / Seitwärts / Abwärts]
50-Tage: [darüber/darunter, X%] | 200-Tage: [darüber/darunter, X%]
RSI (14): [Wert + Interpretation]
Support: $XXX | Resistance: $XXX
52W-Hoch-Nähe: [X% entfernt]

─── SHORT INTEREST & SQUEEZE ───
SI: X% des Floats | Days-to-Cover: X Tage
Trend (4W): [steigend / fallend / stabil]
Squeeze-Risiko bei Beat: [niedrig / mittel / hoch]

─── INSIDER-AKTIVITÄT (90 Tage) ───
Käufe: [Anzahl, Gesamtwert, % der Position]
Verkäufe: [Anzahl, Gesamtwert, % der Position]
Einordnung: [Normal / Auffällig bullisch / Auffällig bärisch]

─── LEADERSHIP & GUIDANCE ───
CEO seit: [X Monate/Jahre]
Änderungen letzte 6 Monate: [Details oder "Keine"]
Guidance-Trend: [Kern-Metrik + Richtung über letzte 3 Quartale]
Letztes Update: [angehoben / bestätigt / gesenkt]

─── OPTIONEN-VORSCHLAG ───
IV: X% | IV-Rank: X% | IV vs. Ø: [hoch / normal / niedrig]
Vorschlag: [Konkreter Spread mit Strikes, Expiry, Max-Risiko]

─── SEKTOR & MAKRO ───
Sektor-Regime: [bullisch / neutral / bärisch]
Relative Stärke (4W): [positiv / negativ]
Cross-Signale: [Haben Bellwether bereits gemeldet? Ergebnis?]
Beta: X.XX

═══════════════════════════════════════════════════════
```

---

## 5. Gedächtnis-System

### 5.1 Kurzzeit-Gedächtnis

Eine Supabase-Tabelle `short_term_memory`. Pro Nachricht ein Eintrag mit: Ticker, Datum, Quelle, Array mit 3-5 Stichpunkten (JSONB), FinBERT-Sentiment-Score, Quartal (z.B. "Q1_2026"), und ein Boolean `is_material` für Torpedo-relevante News. Lebensdauer: Von Watchlist-Aufnahme bis Post-Earnings-Review. Danach Archivierung.

### 5.2 Langzeit-Gedächtnis

Eine Supabase-Tabelle `long_term_memory`. Pro Ticker pro Quartal ein Eintrag mit: Tatsächliches und erwartetes EPS/Revenue (Konsens + Whisper), Kursreaktion Tag 1 und Woche 1, die KI-Empfehlung und beide Scores, ob die Richtung richtig lag, Key Learnings (was war prädiktiv, was nicht), Guidance-Richtung, und die Kern-Metrik mit Trend.

### 5.3 Watchlist

Eine Supabase-Tabelle `watchlist`. Pro Ticker: Unternehmensname, Sektor, Aufnahme-Datum, persönliche Notizen, ein Array `cross_signal_tickers` für die Mapping-Tabelle (z.B. "Wenn TSMC meldet, ist das relevant für NVIDIA, AMD, Micron"), und ein Active-Boolean.

Die Cross-Signal-Mappings werden manuell gepflegt — der Trader kennt diese Zusammenhänge besser als jeder Algorithmus. 20-30 Mappings decken 90% der relevanten Verbindungen ab.

### 5.4 Makro-Snapshots

Eine Supabase-Tabelle `macro_snapshots`. Wöchentliche Einträge mit: Fed Rate, Fed-Erwartung, VIX, Credit Spread, Yield Curve Status, Regime-Einschätzung (bullish/cautious/bearish), und Freitext-Notizen für Geopolitik und besondere Events. Dient als historisches Archiv — nach 6 Monaten sieht man Regime-Wechsel und kann die eigenen Makro-Einschätzungen evaluieren.

### 5.5 Bitcoin-Snapshots

Eine Supabase-Tabelle `btc_snapshots`. Wöchentliche Einträge mit: Kurs, Open Interest, Funding Rate, Long/Short Ratio, nächster Long-/Short-Liquidationscluster, DXY, und die Empfehlung der Woche. Ermöglicht Backtesting der BTC-Signale über Zeit.

---

## 6. KI-Kaskade

### Stufe 0 — FinBERT (lokal auf NUC, kostenlos)

Zweck: Headline-Sentiment-Klassifizierung als erster Filter. Läuft als FastAPI-Microservice in Docker auf dem NUC. Input: Einzelne Headlines aus RSS-Feeds und News-APIs. Output: Sentiment-Score (-1 bis +1). Alles unter -0.3 oder über +0.3 wird als relevant weitergeleitet. Performance: 100-200ms pro Headline auf dem i3 — ausreichend für Batch-Processing. Filtert 70-80% des Rauschens, bevor ein einziger API-Call passiert.

### Stufe 1 — DeepSeek V3 API (~5-8€/Monat)

Zweck: Massen-News-Screening und Stichpunkt-Extraktion. Input: Von FinBERT als relevant gefilterte Nachrichten (Volltext). Output: Strukturiertes JSON mit 3-5 Stichpunkten, Kategorie (Earnings/Guidance/Management/Regulatorisch/Sektor), und einem Relevanz-Flag für Torpedo-Alerts. Kosten: $0.28/M Input-Tokens. Prompt wird auf Englisch formuliert (bessere Qualität), Output wird auf Deutsch angefordert.

### Stufe 2 — Kimi K2.5 API (~10-15€/Monat)

Zweck: Tiefenanalyse von Earnings-Call-Transkripten für die Audit-Reports. Input: Vollständiges Transkript (8.000-15.000 Tokens) plus Kontext aus dem Kurzzeit-Gedächtnis (Stichpunkte der letzten Wochen) plus Daten aus dem Langzeit-Gedächtnis (historische Surprises, letzte Guidance). 256K-Kontextfenster schluckt alles in einem Durchgang. Output: Management-Ton-Analyse, Forward-Guidance-Extraktion, Widersprüche zwischen Zahlen und Aussagen, Risikofaktoren. Einsatz: Nur für die 5-8 Audit-Reports pro Woche.

### Stufe 3 — Frontier-Modell als Fallback (~5-10€/Monat)

Zweck: Qualitätssicherung bei kritischen Situationen. Claude oder GPT-5 über Batch-API (50% Rabatt, 24h Bearbeitungszeit). Einsatz: 5-10 Fälle pro Quartal, wo eine zweite Meinung bei besonders komplexen oder widersprüchlichen Datenlagen nötig ist.

### Token-Optimierung

Stichpunkte statt Volltexte im Gedächtnis spart 80-90% der Tokens bei der Report-Generierung. KI-Prompts werden versioniert und getrackt — jede Version bekommt eine Nummer, Post-Earnings-Reviews dokumentieren, welche Prompt-Version verwendet wurde. Strukturierte JSON-Outputs reduzieren Parsing-Aufwand und verhindern unvorhersehbare Antwortlängen.

---

## 7. Nachrichten-Quellen

### 7.1 Primärquellen

Finnhub News API ist die Hauptquelle für kuratierte Finanznews pro Ticker. Kostenlos, API-Pull alle 30 Minuten via n8n. Liefert bereits einen eigenen Sentiment-Score, der als zweite Meinung neben FinBERT dient.

SEC EDGAR RSS wird alle 10 Minuten via n8n gescannt. Form 8-K (materielle Events) und Form 4 (Insider-Transaktionen) sind oft die frühesten Signale — schneller als Drittanbieter-Nachrichtenseiten. Kostenlos, 10 Requests/Sekunde.

FRED (Federal Reserve Economic Data) liefert alle Makro-Daten kostenlos: VIX, Credit Spreads, Yield Curve, Fed Funds Rate, DXY, M2 Geldmenge, und 800.000+ weitere Zeitreihen.

### 7.2 Bezahlte Quellen (Phase 2+)

FMP (Financial Modeling Prep) Starter für ~19€/Monat: Saubere Fundamentaldaten, Analystenschätzungen, historische Earnings, Insider-Daten, S&P 500-Zusammensetzung, Earnings-Kalender.

EODHD für ~20€/Monat: Tiefere historische Kursdaten, Fundamentaldaten, ideal für Backtesting.

Alpha Vantage (~50$/Monat, Phase 3+): Echtzeit-Finanznachrichten mit KI-Sentiment-Scores. Reduziert eigene LLM-Calls für Sentiment-Analyse.

### 7.3 Keine Search Engine als Dauerfeed

Google News API oder Bing News wären zu teuer und liefern zu viel Rauschen. Gezielte Web-Suche nur bei spezifischen Torpedo-Events — wenn z.B. ein 8-K Filing mehr Kontext erfordert.

---

## 8. Bitcoin-Modul

### 8.1 Datenquellen

CoinGlass API (Free Tier + Pro ~30$/Monat): Open Interest, Funding Rates, Liquidation Heatmap mit Cluster-Levels, Long/Short Ratio, Liquidation Map. Das ist die Primärquelle für alles Derivate-bezogene.

FRED (kostenlos): DXY (Dollar-Index), Realzinsen, M2 Geldmenge für Makro-Korrelation.

Glassnode oder CryptoQuant (Free Tier): On-Chain-Daten als Ergänzung — Exchange Inflows/Outflows, Whale-Bewegungen. Optional, Phase 3b.

### 8.2 Wöchentlicher Bitcoin-Report (Teil des Sonntags-Briefings)

```
═══════════════════════════════════════════════════════
BITCOIN — Wöchentlicher Lagebericht
═══════════════════════════════════════════════════════

KURS: $XX.XXX | 7-Tage: +/-X% | 30-Tage: +/-X%

─── LIQUIDITÄTSCLUSTER ───
Long-Liquidation-Cluster: $XX.XXX [Magnetwirkung ↓]
Short-Liquidation-Cluster: $XX.XXX [Magnetwirkung ↑]
Größeres Cluster: [oben / unten]
→ Preis gravitiert wahrscheinlich Richtung [Level]

─── DERIVATE-POSITIONIERUNG ───
Open Interest: $XX Mrd. | Trend: [steigend / fallend / stabil]
Funding Rate: X% [positiv = Longs zahlen, überhebelt long]
Long/Short Ratio: X.XX
→ Markt ist [überhebelt long / überhebelt short / neutral]

─── MAKRO-KORRELATION ───
DXY: [steigend = BTC-Gegenwind / fallend = Rückenwind]
Realzinsen: [Richtung]
M2-Trend: [expansiv = positiv / restriktiv = negativ]
Fed-Erwartung: [Senkung erwartet = positiv für Risk-Assets]

─── EMPFEHLUNG ───
[Long / Short / Abwarten]
Begründung: [2-3 Sätze]
Key-Levels: $XX.XXX (Support) / $XX.XXX (Resistance)
═══════════════════════════════════════════════════════
```

### 8.3 Bitcoin-Alerts (laufend)

Funding Rate extrem (> 0.05% oder < -0.03%): Warnung vor Overleveraging.
Open Interest steigt stark bei seitwärts Preis: Potentieller Squeeze imminent.
Liquidationscluster wird angenähert: "BTC nähert sich $XX.XXX Long-Liquidationszone".
Plötzlicher OI-Drop > 10%: Cascade-Liquidation passiert gerade.

---

## 9. Daten-Stack Übersicht

### 9.1 Kostenlose Quellen (Phase 1)

Finnhub Free Tier: Earnings-Kalender, News-Feed, Sentiment, Short Interest, Insider-Transaktionen, WebSocket für Echtzeit-Kurse. Wichtigste kostenlose Quelle.

FRED: Alle Makro-Daten. VIX, Credit Spreads, Yield Curve, Fed Funds Rate, DXY, M2. 800.000+ Zeitreihen.

SEC EDGAR: Form 8-K, Form 10-Q, Form 4 (Insider). RSS-Feed, 10 Requests/Sekunde. Kostenlos.

yfinance (Python-Bibliothek): Historische Kursdaten, Fundamentaldaten als Backup. Kostenlos, aber Limits beachten.

### 9.2 Bezahlte Quellen

FMP Starter (~19€/Monat): Fundamentaldaten, Bilanzen, Analystenschätzungen, historische Earnings, S&P 500-Zusammensetzung. Sauberste Datenquelle für Earnings-bezogene Informationen.

EODHD (~20€/Monat): Historische Kurse, Fundamentaldaten, Backtesting-Daten. 100.000 API-Calls/Tag.

CoinGlass Pro (~30$/Monat): Bitcoin-Derivate-Daten — Open Interest, Funding Rates, Liquidation Heatmap, Long/Short Ratio.

### 9.3 Spätere Ergänzungen

Alpha Vantage (~50$/Monat): KI-Sentiment-Scores für News, Earnings-Call-Transkripte.
Unusual Whales oder FlowAlgo (~35-40$/Monat): Options-Flow-Daten für Phase 6.
sec-api.io (~45$/Monat): Echtzeit-SEC-Filing-Alerts mit unter 300ms Latenz.

---

## 10. Tech-Stack & Architektur

### 10.1 Übersicht

```
┌───────────────────────────────────────────────────────────┐
│                     VERCEL (Free Tier)                      │
│              Next.js Dashboard + Clerk Auth                  │
└──────────────────────────┬────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────┴────────────────────────────────┐
│                     SUPABASE (Free/Pro)                     │
│  PostgreSQL: Watchlist, Gedächtnis, Scores, Reports, BTC   │
└──────────────────────────┬────────────────────────────────┘
                           │
┌──────────────────────────┴────────────────────────────────┐
│                   NUC i3 / 16GB (ZimaOS + Docker)          │
│                                                             │
│  ┌──────────────┐ ┌──────────┐ ┌────────────────────────┐  │
│  │    n8n        │ │  Redis   │ │  FastAPI Backend        │  │
│  │  (Workflows,  │ │ (Cache,  │ │  + FinBERT Service      │  │
│  │   Cron-Jobs,  │ │  Queue,  │ │  + Report-Engine        │  │
│  │   Alerts)     │ │  Limits) │ │  + Scoring-Logik        │  │
│  └──────┬───────┘ └────┬─────┘ └──────────┬─────────────┘  │
│         └──────────────┴──────────────────┘                 │
└────────────────────────┬────────────────────────────────────┘
                         │ API Calls
       ┌─────────────────┼─────────────────────┐
       │                 │                     │
  ┌────┴─────┐   ┌──────┴──────┐   ┌──────────┴──────────┐
  │ DeepSeek │   │  Kimi K2.5  │   │  Finnhub / FMP /    │
  │   API    │   │    API      │   │  FRED / CoinGlass / │
  └──────────┘   └─────────────┘   │  SEC EDGAR          │
                                   └─────────────────────┘
       ┌────────────────────────────────┐
       │           ALERTS               │
       │  Telegram Bot (primär)         │
       │  E-Mail via n8n (Sonntag)      │
       └────────────────────────────────┘
```

### 10.2 NUC Docker-Container

fastapi-backend (Custom Python, ~2GB RAM): API-Server, FinBERT-Inferenz, Report-Generierungs-Engine, Scoring-Logik, Daten-Pipeline, alle externen API-Integrationen.

redis (redis:7-alpine, ~0.5GB RAM): Caching von API-Responses, Job-Queue für asynchrone Verarbeitung, Rate-Limiting für externe APIs.

n8n (n8n-io/n8n, ~1GB RAM): Workflow-Orchestrierung, Cron-Jobs (Sonntagabend Report-Pipeline, 30-Min News-Check, 10-Min SEC-Scan), Telegram-Bot-Integration, E-Mail-Versand.

Gesamt: ~3.5GB RAM. Lässt 12.5GB Headroom auf dem 16GB NUC.

### 10.3 Entwicklungsumgebung

IDE: Google Antigravity (VS Code Fork, Pro-Abo vorhanden). Repository: GitHub. Sprache: Python (FastAPI) für das Backend — Antigravity schreibt den Code. Deployment: Docker Compose auf NUC via ZimaOS. Frontend: Next.js, deployed auf Vercel.

### 10.4 Secrets-Management

Alle API-Keys (DeepSeek, Kimi, Finnhub, FMP, CoinGlass, Supabase, Telegram Bot Token) werden als Umgebungsvariablen in einer .env-Datei auf dem NUC gespeichert, die NICHT ins GitHub-Repository committed wird. Docker Compose liest die .env-Datei ein. Für Vercel werden die relevanten Keys über das Vercel-Dashboard als Environment Variables gesetzt.

---

## 11. Phasen-Plan für Antigravity

Jede Phase ist eine abgegrenzte Aufgabe. Antigravity-Agenten arbeiten am besten mit klarem Scope — nicht zu viel auf einmal.

### PHASE 1 — Daten-Fundament (Woche 1-2)

Ziel: Watchlist verwalten und automatisch Daten sammeln.

Aufgabe 1: Supabase-Projekt einrichten. Tabellen anlegen: watchlist, short_term_memory, long_term_memory, macro_snapshots, btc_snapshots. Row-Level Security konfigurieren.

Aufgabe 2: FastAPI-Backend Grundgerüst. Docker-Container mit Python 3.11, FastAPI, uvicorn. Health-Check Endpoint. .env-Handling für API-Keys.

Aufgabe 3: Finnhub-Integration. Earnings-Kalender abrufen und in Supabase speichern. News-Feed pro Ticker abrufen. Short Interest abrufen. Insider-Transaktionen abrufen.

Aufgabe 4: FMP-Integration. Fundamentaldaten (P/E, P/S, EPS). Analystenschätzungen. Historische Earnings (Surprises der letzten 8 Quartale).

Aufgabe 5: FRED-Integration. VIX, Credit Spreads (ICE BofA High Yield), Fed Funds Rate, 10Y-2Y Spread (Yield Curve), DXY.

Aufgabe 6: Watchlist-CLI. Einfaches Python-Script: Ticker hinzufügen, entfernen, auflisten, Notizen und Cross-Signal-Mappings setzen.

Ergebnis Phase 1: Ticker auf der Watchlist, System sammelt automatisch alle relevanten Daten in Supabase.

### PHASE 2 — Audit-Report-Pipeline (Woche 3-4)

Ziel: Sonntags-Reports per E-Mail.

Aufgabe 1: FinBERT-Service deployen. Docker-Container mit HuggingFace Transformers, FastAPI-Endpoint /sentiment. Batch-Endpoint für mehrere Headlines gleichzeitig.

Aufgabe 2: DeepSeek-API-Integration. Prompt für News-Zusammenfassung (Englisch, strukturierter JSON-Output). Prompt für Stichpunkt-Extraktion.

Aufgabe 3: Kimi-API-Integration. Prompt für Earnings-Tiefenanalyse (Management-Ton, Guidance-Extraktion, Widersprüche). Input: Transkript + Gedächtnis-Kontext + historische Daten.

Aufgabe 4: Scoring-Engine. Opportunity-Score berechnen (gewichtete Summe aller 9 Faktoren). Torpedo-Score berechnen (gewichtete Summe aller 7 Faktoren). Entscheidungsmatrix anwenden → Empfehlung generieren.

Aufgabe 5: Report-Generator. Alle Daten zusammenführen + KI-Analyse → strukturierter Audit-Report nach Template. Makro-Header generieren aus FRED-Daten + KI-Interpretation.

Aufgabe 6: E-Mail-Pipeline. n8n-Workflow: Cron-Job Sonntagabend 20:00 → Report-Pipeline triggern → HTML-E-Mail mit Makro-Header + Reports versenden.

Ergebnis Phase 2: Jeden Sonntag eine E-Mail mit Makro-Header und Audit-Reports für alle meldenden Watchlist-Titel.

### PHASE 3 — News-Pipeline & Alerts (Woche 5-6)

Ziel: Laufende News-Erfassung, Telegram-Alerts, Torpedo-Warnungen.

Aufgabe 1: n8n-Workflow für Finnhub News. Alle 30 Min. News für Watchlist-Ticker abrufen. FinBERT-Filterung. DeepSeek-Stichpunkt-Extraktion. Speicherung im Kurzzeit-Gedächtnis.

Aufgabe 2: n8n-Workflow für SEC EDGAR RSS. Alle 10 Min. scannen. Form 8-K und Form 4 erkennen. Schlüsselwort-Matching für Torpedo-Events.

Aufgabe 3: Telegram-Bot einrichten. Bot-Token erstellen. Alert-Templates definieren (News, Torpedo, Makro). n8n-Integration für automatischen Versand.

Aufgabe 4: Torpedo-Logik. Definieren, welche Events einen Alert auslösen: Insider-Verkauf > 5% der Position, 8-K mit Risiko-Keywords, Analysten-Downgrade, Management-Abgang.

Aufgabe 5: Makro-Trigger-Alerts. Wichtige Wirtschaftsdaten-Termine in den Kalender (NFP, CPI, FOMC). Bei Veröffentlichung: Automatisch FRED-Daten abrufen, Abweichung vom Konsens berechnen, Alert mit Einordnung senden.

Ergebnis Phase 3: Relevante News per Telegram-Push. Stichpunkte fließen automatisch in nächsten Audit-Report. Torpedo-Warnungen bei kritischen Events.

### PHASE 3b — Bitcoin-Modul (parallel zu Phase 3)

Ziel: Bitcoin-Lagebericht und Derivate-Alerts.

Aufgabe 1: CoinGlass-API-Integration. Open Interest, Funding Rates, Liquidation Heatmap/Map, Long/Short Ratio abrufen und in btc_snapshots speichern.

Aufgabe 2: FRED-Integration für BTC. DXY und M2 bereits vorhanden, nur BTC-spezifische Korrelationslogik hinzufügen.

Aufgabe 3: Bitcoin-Report-Template. Teil des Sonntags-Briefings. Strukturierter Report nach Template.

Aufgabe 4: BTC Telegram-Alerts. Extreme Funding Rates, OI-Anomalien, Cluster-Annäherung.

Ergebnis Phase 3b: Bitcoin-Lagebericht im Sonntags-Briefing. Laufende Alerts bei extremen Derivate-Levels.

### PHASE 4 — Feedback-Loop (Woche 7-8)

Ziel: Post-Earnings-Reviews, Confidence-Tracking, Lernfähigkeit.

Aufgabe 1: Post-Earnings-Daten automatisch abrufen. Actual EPS/Revenue (FMP), Kursreaktion Tag 1 und Tag 5 (yfinance).

Aufgabe 2: Automatischer Vergleich. KI-Empfehlung vs. tatsächliches Ergebnis. Richtung richtig? Magnitude richtig? Welche Score-Komponenten waren am prädiktivsten?

Aufgabe 3: Langzeit-Gedächtnis befüllen. Alle Daten strukturiert archivieren.

Aufgabe 4: Aggregierte Auswertung. Quartals-Report: Trefferquote nach Score-Bereich, nach Sektor, nach Trade-Typ.

Aufgabe 5: Prompt-Versionierung. Jeder Prompt bekommt eine Versionsnummer. Post-Earnings-Reviews dokumentieren die verwendete Version. A/B-Testing verschiedener Prompt-Varianten.

Ergebnis Phase 4: System dokumentiert automatisch seine eigene Treffsicherheit und liefert Daten für kontinuierliche Verbesserung.

### PHASE 5 — Web-Dashboard (Woche 9-12)

Ziel: Visuelle Zentrale, erreichbar von überall.

Next.js auf Vercel. Watchlist-Verwaltung (hinzufügen, entfernen, Notizen, Cross-Signal-Mappings). Report-Anzeige mit Scores und Empfehlungen. Makro-Dashboard (VIX-Chart, Yield Curve, Sektor-Heatmap). Bitcoin-Dashboard (OI, Funding, Liquidation-Levels). Gedächtnis-Ansicht pro Ticker (Timeline der News + historische Earnings). Performance-Dashboard (Trefferquote über Zeit, Confidence-Score-Verteilung). Earnings-Kalender visuell.

### PHASE 6 — Optionen & Broker (später)

Options-Daten-Integration (IV, Options-Flow, Unusual Activity via Unusual Whales / FlowAlgo). Options-Vorschlag-Engine: Konkreter Spread-Vorschlag basierend auf Report-Empfehlung, IV-Level und definiertem Max-Risiko. IBKR Paper-Trading-Anbindung. Halbautomatisierter Flow: Report → Bestätigung → Order.

---

## 12. Kosten-Übersicht

### Phase 1-3 (MVP)

Supabase Free Tier: 0€. Vercel Free Tier: 0€. NUC Strom: ~5€. Finnhub Free: 0€. FRED: 0€. SEC EDGAR: 0€. FMP Starter: ~19€. DeepSeek API: ~5-8€. Kimi K2.5 API: ~10-15€. CoinGlass Pro: ~30€. Telegram: 0€. Gesamt MVP: ~70-80€/Monat.

### Voll ausgebaut

Zusätzlich: EODHD ~20€. Alpha Vantage ~50€. Unusual Whales ~35€. Frontier-Fallback ~5-10€. Gesamt: ~180-195€/Monat.

Empfehlung: Mit dem MVP starten (~70-80€), erst nach bewiesenem Wert auf Premium-Quellen skalieren.

---

## 13. Design-Entscheidungen

Reports auf Deutsch, KI-Prompts auf Englisch (bessere Qualität), Outputs werden auf Deutsch angefordert. MVP-first — jede Phase liefert ein funktionsfähiges Ergebnis. Supabase statt lokale DB — minimiert Admin-Aufwand. Antigravity-kompatibel — jede Phase ist eine klar abgegrenzte Aufgabe für die Agenten, nicht zu viel Scope auf einmal. Token-Sparsamkeit — Stichpunkte statt Volltexte, strukturierte Prompts, Model-Kaskadierung. Broker-agnostisch — IBKR-Integration als eigene Phase, Plattform funktioniert ohne. Bewertung ist regime-kontextuell — kein absolutes "teuer/günstig", immer relativ zur Narrative. Kein autonomer Trading-Bot — die Plattform empfiehlt, der Mensch entscheidet.

---

## 14. Offene Punkte für spätere Iterationen

GPU-Upgrade für NUC → lokale LLM-Inferenz, amortisiert sich in 12-18 Monaten bei konstanten API-Kosten.

Backtesting-Modul mit Walk-Forward-Validierung — wie hätten die Scores historisch performt?

Deutsche Steueroptimierung — Abgeltungssteuer-Logging, 20.000€ Verlustverrechnungsdeckel bei Termingeschäften, automatische Aufbereitung für die Steuererklärung.

Sektor-Kaskade als Signal — frühe Reporter in einem Sektor prognostizieren späte Reporter (akademisch validiert). System trackt automatisch: "TSMC hat stark gemeldet → Erhöht Wahrscheinlichkeit für AMD/NVIDIA-Beat."

Dark-Pool-Aktivität (FINRA-Daten, 2-4 Wochen Verzögerung) als institutionelles Akkumulationssignal.

Social Sentiment (StockTwits API, Reddit via PRAW) als konträrer Indikator.

Congressional Trading Daten — interessant, aber 45-Tage Meldefrist begrenzt den Timing-Wert.

Whisper Number Automation — aktuell manuell, später eventuell eigenes Modell basierend auf Analystenschätzungs-Trends und historischen Mustern.
