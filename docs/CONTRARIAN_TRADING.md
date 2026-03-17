# Contrarian-Trading-System

## Überblick

Das Contrarian-Trading-System identifiziert systematisch überverkaufte Quality-Stocks mit extrem negativem Sentiment aber intakten Fundamentals. Es ist speziell für News-Trading vor/zwischen Earnings konzipiert und fokussiert sich auf Aktien mit hohem Beta (>1.2).

## Kernkonzept: Mismatch-Score

Der **Mismatch-Score** (0-100) ist die zentrale Metrik und misst die Diskrepanz zwischen:
- **Markt-Sentiment** (extrem negativ)
- **Fundamentale Qualität** (intakt/gut)
- **Volatilität** (hoch = große Trading-Chancen)

### Trigger-Kriterien

Ein Contrarian-Setup liegt vor, wenn:
1. **Sentiment** < -0.5 (7-Tage-Durchschnitt extrem negativ)
2. **Quality Score** > 6/10 (Fundamentals intakt)
3. **Beta** > 1.2 (volatile Aktie mit starken Bewegungen)
4. **Mismatch Score** > 50/100

## Komponenten

### 1. Quality Score (0-10)

Bewertet die fundamentale Stärke eines Unternehmens:

**Komponenten:**
- **Debt-to-Equity** < 1.5 → 3 Punkte
- **Current Ratio** > 1.2 → 3 Punkte  
- **Free Cash Flow Yield** > 0% → 4 Punkte

**Value Trap Detection:**
- Hohe Schulden (D/E > 2.0) + negativer FCF = -5 Punkte Strafe
- Kritische Verschuldung (D/E > 3.0) = -2 Punkte Strafe

**Funktion:** `backend.app.analysis.scoring.calculate_quality_score()`

### 2. Mismatch Score (0-100)

Bewertet die Contrarian-Opportunity:

**Komponenten:**
- **Sentiment** (max 40 Punkte)
  - < -0.7: 40 Punkte (extremer Pessimismus)
  - < -0.5: 30 Punkte (starker Pessimismus)
  - < -0.3: 20 Punkte (moderater Pessimismus)

- **Quality** (max 30 Punkte)
  - ≥ 8.0: 30 Punkte (exzellente Fundamentals)
  - ≥ 6.0: 25 Punkte (gute Fundamentals)
  - ≥ 4.0: 15 Punkte (akzeptable Fundamentals)

- **Beta** (max 20 Punkte)
  - ≥ 1.5: 20 Punkte (sehr volatile Aktie)
  - ≥ 1.2: 15 Punkte (volatile Aktie)
  - ≥ 1.0: 10 Punkte (durchschnittlich)

- **Options-Timing** (max 10 Punkte Bonus)
  - IV < Hist Vol (Spread < -5%): +10 Punkte (günstige Optionen)
  - IV ≈ Hist Vol: +7 Punkte (neutrale Optionen)
  - IV > Hist Vol (Spread > 10%): +0 Punkte (teure Optionen)

- **Contrarian-Boost**: +10 Punkte wenn alle Kriterien erfüllt

**Funktion:** `backend.app.analysis.scoring.calculate_mismatch_score()`

### 3. Options-Timing

**Implizite Volatilität (IV) ATM:**
- Durchschnitt aus ATM Call + Put IV der nächsten Expiration (> 5 Tage)
- Vergleich mit historischer Volatilität (20 Tage)

**IV Spread = IV ATM - Historische Volatilität**
- Spread > +10%: Optionen TEUER → Gefahr von IV Crush
- Spread ± 5%: Optionen NEUTRAL
- Spread < -5%: Optionen GÜNSTIG → Entry-Opportunity

## API-Endpoints

### 1. Options-Daten abrufen
```
GET /api/data/options/{ticker}
```

**Response:**
```json
{
  "ticker": "AAPL",
  "implied_volatility_atm": 35.2,
  "options_volume": 125000,
  "put_call_ratio": 1.15,
  "historical_volatility": 28.5,
  "expiration_date": "2026-04-18",
  "iv_percentile": null
}
```

### 2. Risk-Metriken abrufen
```
GET /api/data/risk-metrics/{ticker}
```

**Response:**
```json
{
  "ticker": "AAPL",
  "beta": 1.35,
  "historical_volatility_20d": 28.5,
  "historical_volatility_60d": 32.1
}
```

### 3. Contrarian-Opportunities finden
```
GET /api/data/contrarian-opportunities?min_mismatch_score=50
```

**Response:**
```json
{
  "status": "success",
  "count": 3,
  "opportunities": [
    {
      "ticker": "AAPL",
      "mismatch_score": 75.5,
      "sentiment_7d": -0.65,
      "quality_score": 8.5,
      "beta": 1.35,
      "iv_atm": 35.2,
      "hist_vol": 28.5,
      "iv_spread": 6.7,
      "material_news_count": 4,
      "debt_to_equity": 1.2,
      "current_ratio": 1.8,
      "fcf_yield": 0.045
    }
  ]
}
```

## LLM-Prompts

### 1. Torpedo Alert Prompt (`prompts/torpedo_alert.md`)

Erweitert um Contrarian-Analyse mit **Pflichtfragen:**

1. **VALUE TRAP vs. ÜBERTREIBUNG?**
   - Ist die Verschuldung tragbar oder kritisch?
   - Ist der Free Cash Flow stabil oder sinkend?
   - Gibt es strukturelle Probleme?

2. **OPTIONS-TIMING: IV ZU TEUER?**
   - Ist die IV deutlich höher als die historische Vola?
   - Besteht Gefahr eines IV Crush vor Earnings?
   - Sind Aktien oder Optionen das bessere Instrument?

### 2. Morning Briefing Prompt (`prompts/morning_briefing.md`)

Neue Sektion: **CONTRARIAN-OPPORTUNITIES**
- Zeigt Ticker mit hohem Mismatch-Score
- Inkl. Beta, Quality, IV Spread, Fundamentals
- Trade-Ideen (Aktien/Calls/Puts mit Strike/Expiration)

### 3. Audit Report Prompt (`prompts/audit_report.md`)

Neue Pflicht-Sektion bei Mismatch-Score > 50:
- Contrarian-Analyse mit den 2 Pflichtfragen
- Value Trap Detection
- Options-Timing-Bewertung

## Datenfluss

```
1. Watchlist-Ticker
   ↓
2. News Memory → Sentiment 7-Tage-Durchschnitt
   ↓
3. FMP Key Metrics → Quality Score berechnen
   ↓
4. YFinance → Beta + Historische Volatilität
   ↓
5. YFinance Options → IV ATM + Put/Call Ratio
   ↓
6. Mismatch Score berechnen
   ↓
7. Filter: Sentiment < -0.5, Quality > 6, Beta > 1.2, Mismatch > 50
   ↓
8. Contrarian-Opportunities-Liste (sortiert nach Mismatch Score)
```

## Schemas

### `schemas/options.py`
- `OptionsData`: IV ATM, Volume, Put/Call Ratio, Hist Vol, Expiration
- `OptionChainSummary`: Aggregierte Calls/Puts-Daten

### `schemas/scores.py`
- `OpportunityScore`: Erweitert um `beta`, `quality_score`, `mismatch_score`

### `schemas/technicals.py`
- `TechnicalSetup`: Erweitert um `historical_volatility_20d`, `historical_volatility_60d`, `beta`

### `schemas/valuation.py`
- `ValuationData`: Erweitert um `debt_to_equity`, `current_ratio`, `free_cash_flow_yield`

## Verwendung

### Backend

```python
from backend.app.data.yfinance_data import get_risk_metrics, get_atm_implied_volatility
from backend.app.data.fmp import get_key_metrics
from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score

# 1. Beta holen
risk_data = await get_risk_metrics("AAPL")
beta = risk_data["beta"]

# 2. Options-Daten holen
options_data = await get_atm_implied_volatility("AAPL")
iv_atm = options_data.implied_volatility_atm
hist_vol = options_data.historical_volatility

# 3. Quality Score berechnen
key_metrics = await get_key_metrics("AAPL")
quality_score = calculate_quality_score(
    debt_to_equity=key_metrics.debt_to_equity,
    current_ratio=key_metrics.current_ratio,
    free_cash_flow_yield=key_metrics.free_cash_flow_yield
)

# 4. Mismatch Score berechnen
mismatch_score = calculate_mismatch_score(
    sentiment_score=-0.65,
    quality_score=quality_score,
    beta=beta,
    iv_atm=iv_atm,
    hist_vol=hist_vol
)
```

### Frontend

```javascript
// Contrarian-Opportunities abrufen
const response = await fetch('http://localhost:8000/api/data/contrarian-opportunities?min_mismatch_score=50');
const data = await response.json();

data.opportunities.forEach(opp => {
  console.log(`${opp.ticker}: Mismatch=${opp.mismatch_score}, Quality=${opp.quality_score}, Beta=${opp.beta}`);
});
```

## Error-Handling

Alle Funktionen sind graceful-fail-safe:

- **Keine Options-Daten**: Funktion gibt `None` zurück, Ticker wird übersprungen
- **Kein Beta**: Beta = `None`, Ticker wird in Contrarian-Liste nicht aufgenommen
- **Keine Key Metrics**: Quality Score kann nicht berechnet werden, Ticker wird übersprungen
- **API-Fehler**: Logging + Fortsetzung mit nächstem Ticker

## Trading-Workflow

1. **Screening**: `/api/data/contrarian-opportunities` aufrufen
2. **Analyse**: Für jeden Ticker Torpedo Alert oder Audit Report generieren
3. **Value Trap Check**: LLM beantwortet Pflichtfrage 1
4. **Options-Timing**: LLM beantwortet Pflichtfrage 2
5. **Entry**: 
   - Wenn Value Trap NEIN + IV günstig → Calls kaufen
   - Wenn Value Trap NEIN + IV teuer → Aktien kaufen
   - Wenn Value Trap UNKLAR → Beobachten
   - Wenn Value Trap JA → Ignorieren/Short

## Risikomanagement

- **Position Sizing**: Bei Beta > 1.5 kleinere Positionen
- **Stop Loss**: Bei fundamentaler Verschlechterung (FCF dreht negativ)
- **IV Crush Protection**: Keine Calls kurz vor Earnings wenn IV > Hist Vol + 10%
- **Value Trap Exit**: Sofortiger Exit bei strukturellen Problemen (Downsizing, Leadership-Wechsel)

## Nächste Schritte (Optional)

1. **IV Percentile**: Historische IV-Daten sammeln → IV Percentile berechnen
2. **Backtest**: Performance historischer Contrarian-Setups messen
3. **Alert-System**: Telegram-Benachrichtigung bei neuem High-Mismatch-Setup
4. **Options-Scanner**: Automatische Suche nach günstigen Calls/Puts bei Contrarian-Setups
