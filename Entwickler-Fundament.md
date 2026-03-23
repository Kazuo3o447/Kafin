# ANTIGRAVITY TRADING PLATFORM — Entwickler-Fundament
## Das Briefing für autonome Agenten
### Stand: 7. März 2026

---

# TEIL 1: ROOT-CONTEXT (wird zu CLAUDE.md im Repository)

```markdown
# Antigravity Trading Platform

## Was ist das?
Eine KI-gestützte Earnings-Trading-Plattform. Sie sammelt Finanzdaten, analysiert sie
mit einer KI-Kaskade und generiert wöchentliche Audit-Reports mit Handlungsempfehlungen
für Aktien-Earnings und Bitcoin. Der Trader entscheidet — die Plattform empfiehlt.

## Architektur
- Backend: Python FastAPI auf NUC (ZimaOS + Docker)
- Datenbank: Supabase (gehostetes PostgreSQL)
- Frontend: Next.js auf Vercel (Phase 5)
- KI: FinBERT (lokal) → DeepSeek API → Groq API
- Alerts: Telegram Bot + E-Mail via n8n
- Bitcoin: CoinGlass API für Derivate-Daten

## Regeln für Agenten

### Bevor du arbeitest
1. Lies die README.md im Modulordner, an dem du arbeitest
2. Lies die relevanten Schemas in `schemas/`
3. Lies die API-Docs in `docs/apis/` wenn du eine externe API nutzt
4. Prüfe `STATUS.md` ob abhängige Module fertig sind

### Code-Konventionen
- Sprache: Python 3.11+, Type Hints überall
- Naming: snake_case für Variablen/Funktionen, PascalCase für Klassen
- Kommentare und Docs: Deutsch
- Code: Englisch
- Jede Datei beginnt mit einem Header-Docstring (siehe Template unten)
- HTTP-Client: httpx (nicht requests, nicht aiohttp)
- Schemas: Pydantic v2 Models aus `schemas/`
- Datenbank: supabase-py Client aus `backend/app/db.py`
- Config: Alles aus `config/` laden, nie hardcoden
- Secrets: Aus Environment-Variablen via `backend/app/config.py`, NIE im Code

### Error-Handling
- Jeder externe API-Call in try/except
- Bei Fehler: logger.error() mit Kontext (API, Ticker, Endpoint)
- Rate-Limit-Fehler: Retry mit Backoff via den zentralen Rate-Limiter
- Fehlende Daten: None zurückgeben + loggen, nie stilles Verschlucken

### Logging
- Nutze `from backend.app.logger import get_logger`
- Format: `logger = get_logger(__name__)`
- Levels: DEBUG für API-Responses, INFO für Workflow-Schritte, WARNING für Fallbacks, ERROR für Fehler

### Mock-Daten
- Prüfe `config/settings.yaml` → `use_mock_data: true/false`
- Wenn true: Lade Daten aus `fixtures/` statt echte API-Calls
- Jedes Daten-Modul MUSS beide Pfade unterstützen
- Pattern: `if settings.use_mock_data: return load_fixture("finnhub_earnings.json")`

### Tests
- Jedes Modul bekommt eine `test_[modul].py`
- Mindestens ein Smoke-Test: "Kommt das erwartete Schema zurück?"
- Tests nutzen IMMER Mock-Daten, nie echte API-Calls

### Dependencies
- Nutze NUR Bibliotheken aus `requirements.txt`
- Brauchst du etwas Neues: Kommentar in STATUS.md, nicht selbst installieren

### Datei-Header-Template
Jede .py-Datei beginnt so:
"""
[Modulname] — [Kurzbeschreibung in einem Satz]

Input:  [Was kommt rein? Welches Schema?]
Output: [Was kommt raus? Welches Schema?]
Deps:   [Welche anderen Module werden genutzt?]
Config: [Welche Config-Werte werden gelesen?]
API:    [Welche externe API wird aufgerufen? Oder "Keine"]
"""

## Verzeichnisstruktur
docs/           → Spezifikation, API-Docs, Architektur
docs/apis/      → Eine Datei pro externer API mit Endpoints + Formaten
config/         → YAML-Dateien für alle konfigurierbaren Werte
schemas/        → Pydantic Models als Verträge zwischen Modulen
prompts/        → KI-Prompts als Markdown, versioniert
fixtures/       → Mock-Daten (echte API-Responses als JSON)
backend/app/    → FastAPI-Anwendung
backend/app/data/       → Daten-Module (eine Datei pro API)
backend/app/analysis/   → KI-Kaskade + Scoring + Report-Generator
backend/app/memory/     → Gedächtnis-System (Supabase CRUD)
backend/app/alerts/     → Telegram + E-Mail
database/       → SQL-Schema-Definitionen
tests/          → Test-Dateien
```

---

# TEIL 2: KONFIGURATIONS-ARCHITEKTUR

## config/settings.yaml
```yaml
# ═══════════════════════════════════════════
# Globale Plattform-Einstellungen
# ═══════════════════════════════════════════

# Entwicklung vs. Produktion
environment: "development"    # "development" | "production"
use_mock_data: true           # true = Fixtures statt echte API-Calls
log_level: "DEBUG"            # DEBUG | INFO | WARNING | ERROR

# Sprache der Reports
report_language: "de"
prompt_language: "en"         # Prompts auf Englisch → bessere KI-Qualität
```

## config/scoring.yaml
```yaml
# ═══════════════════════════════════════════
# Scoring-Gewichtungen
# Ändern dieser Werte erfordert KEINEN Code-Change
# ═══════════════════════════════════════════

opportunity_score:
  earnings_momentum: 0.15
  whisper_delta: 0.15
  valuation_regime: 0.15
  guidance_trend: 0.15
  technical_setup: 0.10
  sector_regime: 0.10
  short_squeeze_potential: 0.10
  insider_activity: 0.05
  options_flow: 0.05

torpedo_score:
  valuation_downside: 0.20
  expectation_gap: 0.20
  insider_selling: 0.15
  guidance_deceleration: 0.15
  leadership_instability: 0.10
  technical_downtrend: 0.10
  macro_headwind: 0.10

# Entscheidungs-Schwellenwerte
thresholds:
  strong_buy_min_opportunity: 7
  strong_buy_max_torpedo: 3
  strong_short_max_opportunity: 3
  strong_short_min_torpedo: 7
  watch_min_torpedo: 7
```

## config/alerts.yaml
```yaml
# ═══════════════════════════════════════════
# Alert-Schwellenwerte und Zeitpläne
# ═══════════════════════════════════════════

# FinBERT-Filter
finbert:
  relevance_threshold: 0.3    # Absoluter Sentiment-Score ab dem News relevant sind

# Torpedo-Alerts
torpedo:
  insider_sell_threshold: 0.05  # Alert wenn Insider > 5% der Position verkauft
  keywords:                     # 8-K Keywords die sofort Alert auslösen
    - "investigation"
    - "subpoena"
    - "restatement"
    - "SEC inquiry"
    - "class action"
    - "resignation"            # C-Suite Rücktritt

# Bitcoin-Alerts
bitcoin:
  funding_rate_extreme_high: 0.05
  funding_rate_extreme_low: -0.03
  oi_drop_alert_percent: 10     # Alert bei OI-Drop > 10%

# Zeitpläne (Cron-Syntax)
schedules:
  sunday_report: "0 20 * * 0"      # Sonntag 20:00 Uhr
  news_check: "*/30 * * * *"       # Alle 30 Minuten
  sec_edgar_scan: "*/10 * * * *"   # Alle 10 Minuten
  btc_data_pull: "0 */4 * * *"     # Alle 4 Stunden
```

## config/apis.yaml
```yaml
# ═══════════════════════════════════════════
# API-Konfiguration und Rate-Limits
# API-Keys kommen aus .env, NICHT hierher
# ═══════════════════════════════════════════

finnhub:
  base_url: "https://finnhub.io/api/v1"
  rate_limit_per_minute: 60
  retry_max: 3
  retry_backoff_seconds: 2

fmp:
  base_url: "https://financialmodelingprep.com/api/v3"
  rate_limit_per_minute: 300
  retry_max: 3
  retry_backoff_seconds: 1

fred:
  base_url: "https://api.stlouisfed.org/fred"
  rate_limit_per_minute: 120
  retry_max: 3
  retry_backoff_seconds: 1

deepseek:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 4096
  temperature: 0.3
  rate_limit_per_minute: 60
  retry_max: 2
  retry_backoff_seconds: 5

kimi:
  base_url: "https://api.moonshot.cn/v1"
  model: "moonshot-v1-auto"
  max_tokens: 8192
  temperature: 0.3
  rate_limit_per_minute: 30
  retry_max: 2
  retry_backoff_seconds: 10

coinglass:
  base_url: "https://open-api-v3.coinglass.com/api"
  rate_limit_per_minute: 30
  retry_max: 3
  retry_backoff_seconds: 5

supabase:
  # URL und Key kommen aus .env
  timeout_seconds: 30
```

## .env.example
```bash
# ═══════════════════════════════════════════
# API-Keys — NIEMALS ins Repository committen
# Kopiere diese Datei zu .env und fülle die Werte
# ═══════════════════════════════════════════

# Finanzdaten
FINNHUB_API_KEY=
FMP_API_KEY=
FRED_API_KEY=
COINGLASS_API_KEY=

# KI-Modelle
DEEPSEEK_API_KEY=
KIMI_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_KEY=

# Alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EMAIL_SMTP_HOST=
EMAIL_SMTP_USER=
EMAIL_SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

---

# TEIL 3: SCHEMAS (Verträge zwischen Modulen)

## schemas/earnings.py
```python
"""
Earnings-Daten-Schemas — Verträge für alle Earnings-bezogenen Daten.

Jedes Daten-Modul das Earnings-Daten liefert MUSS diese Schemas verwenden.
Jedes Analyse-Modul das Earnings-Daten konsumiert KANN sich auf diese Felder verlassen.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EarningsExpectation(BaseModel):
    """Erwartungen vor den Earnings."""
    ticker: str
    report_date: datetime
    report_timing: str                    # "pre_market" | "after_hours"
    eps_consensus: Optional[float]
    eps_whisper: Optional[float]
    revenue_consensus: Optional[float]
    revenue_whisper: Optional[float]
    analyst_count: Optional[int]          # Anzahl der Analysten mit Schätzungen


class EarningsHistory(BaseModel):
    """Historische Earnings-Daten eines Quartals."""
    ticker: str
    quarter: str                          # z.B. "Q4_2025"
    eps_actual: float
    eps_consensus: float
    eps_surprise_percent: float
    revenue_actual: float
    revenue_consensus: float
    revenue_surprise_percent: float
    stock_reaction_1d: Optional[float]    # Kursreaktion Tag 1 in %
    stock_reaction_5d: Optional[float]    # Kursreaktion Woche 1 in %
    guidance_direction: Optional[str]     # "raised" | "maintained" | "lowered"


class EarningsHistorySummary(BaseModel):
    """Zusammenfassung der letzten 8 Quartale."""
    ticker: str
    quarters_beat: int                    # Wie oft geschlagen?
    quarters_missed: int
    avg_surprise_percent: float
    last_quarter: EarningsHistory
    all_quarters: list[EarningsHistory]
```

## schemas/valuation.py
```python
"""
Bewertungs-Schemas — Regime-kontextuelle Bewertungsdaten.
"""

from pydantic import BaseModel
from typing import Optional


class ValuationData(BaseModel):
    """Bewertungskennzahlen eines Tickers."""
    ticker: str
    pe_ratio: Optional[float]
    ps_ratio: Optional[float]
    pe_sector_median: Optional[float]
    ps_sector_median: Optional[float]
    pe_own_3y_median: Optional[float]     # Eigener 3-Jahres-Median
    ps_own_3y_median: Optional[float]
    market_cap: Optional[float]
    sector: str
    industry: str


class ValuationRegimeAnalysis(BaseModel):
    """KI-generierte Regime-Analyse."""
    ticker: str
    current_regime: str                   # z.B. "Pharma", "Biotech-Plattform", "SaaS Growth"
    regime_shift_detected: bool
    potential_regime: Optional[str]       # Wohin könnte sich das Regime verschieben?
    upside_if_rerating: Optional[str]     # Freitext-Einschätzung
    downside_if_narrative_breaks: Optional[str]
```

## schemas/technicals.py
```python
"""
Technische Analyse Schemas.
"""

from pydantic import BaseModel
from typing import Optional


class TechnicalSetup(BaseModel):
    """Technische Kennzahlen eines Tickers."""
    ticker: str
    current_price: float
    sma_50: Optional[float]
    sma_200: Optional[float]
    rsi_14: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    high_52w: Optional[float]
    low_52w: Optional[float]
    distance_to_52w_high_percent: Optional[float]
    trend: str                            # "uptrend" | "sideways" | "downtrend"
    above_sma50: bool
    above_sma200: bool
```

## schemas/sentiment.py
```python
"""
Sentiment- und News-Schemas.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class NewsBulletPoint(BaseModel):
    """Einzelner News-Stichpunkt im Gedächtnis."""
    ticker: str
    date: datetime
    source: str
    bullet_points: list[str]              # 3-5 Stichpunkte
    sentiment_score: float                # FinBERT: -1 bis +1
    category: str                         # "earnings" | "guidance" | "management" | "regulatory" | "sector"
    is_material: bool                     # Torpedo-relevant?


class InsiderActivity(BaseModel):
    """Insider-Transaktionen der letzten 90 Tage."""
    ticker: str
    total_buys: int
    total_buy_value: float
    total_sells: int
    total_sell_value: float
    largest_sell_percent_of_position: Optional[float]
    is_cluster_buy: bool                  # Mehrere Insider kaufen gleichzeitig
    is_cluster_sell: bool
    assessment: str                       # "normal" | "bullish" | "bearish"


class ShortInterestData(BaseModel):
    """Short-Interest-Daten."""
    ticker: str
    short_interest_percent: float         # % des Floats
    days_to_cover: float
    short_interest_trend: str             # "rising" | "falling" | "stable"
    squeeze_risk: str                     # "low" | "medium" | "high"
```

## schemas/scores.py
```python
"""
Scoring-Schemas — Output der Scoring-Engine.
"""

from pydantic import BaseModel
from typing import Optional


class OpportunityScore(BaseModel):
    """Detaillierter Opportunity-Score mit Einzelfaktoren."""
    ticker: str
    total_score: float                    # 1-10
    earnings_momentum: float
    whisper_delta: float
    valuation_regime: float
    guidance_trend: float
    technical_setup: float
    sector_regime: float
    short_squeeze_potential: float
    insider_activity: float
    options_flow: float


class TorpedoScore(BaseModel):
    """Detaillierter Torpedo-Score mit Einzelfaktoren."""
    ticker: str
    total_score: float                    # 1-10
    valuation_downside: float
    expectation_gap: float
    insider_selling: float
    guidance_deceleration: float
    leadership_instability: float
    technical_downtrend: float
    macro_headwind: float


class AuditRecommendation(BaseModel):
    """Finale Empfehlung aus der Entscheidungsmatrix."""
    ticker: str
    opportunity_score: OpportunityScore
    torpedo_score: TorpedoScore
    recommendation: str                   # "strong_buy" | "buy" | "hold" | "short" | "strong_short" | "watch" | "ignore"
    recommendation_label: str             # Deutsche Bezeichnung
    reasoning: str                        # KI-generierte Begründung
    options_suggestion: Optional[str]     # Optionsvorschlag wenn relevant
```

## schemas/macro.py
```python
"""
Makro-Daten-Schemas.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MacroSnapshot(BaseModel):
    """Wöchentlicher Makro-Snapshot."""
    date: datetime
    fed_rate: float
    fed_expectation: str                  # z.B. "Senkung erwartet Q2"
    vix: float
    credit_spread_bps: float              # High-Yield Spread in Basispunkten
    yield_curve: str                      # "positive" | "flat" | "inverted"
    dxy: Optional[float]
    regime: str                           # "bullish" | "cautious" | "bearish"
    index_shorts_recommended: bool
    instrument_suggestions: Optional[str] # Wenn bärisch: Welche Instrumente?
    geopolitical_notes: Optional[str]


class BitcoinSnapshot(BaseModel):
    """Wöchentlicher Bitcoin-Snapshot."""
    date: datetime
    price: float
    price_7d_change_percent: float
    open_interest_usd: float
    open_interest_trend: str              # "rising" | "falling" | "stable"
    funding_rate: float
    long_short_ratio: float
    liquidation_cluster_long: Optional[float]   # Nächster Long-Liquidation-Level
    liquidation_cluster_short: Optional[float]  # Nächster Short-Liquidation-Level
    dxy: Optional[float]
    recommendation: str                   # "long" | "short" | "wait"
    reasoning: str
    key_support: Optional[float]
    key_resistance: Optional[float]
```

---

# TEIL 4: DATENBANK-SCHEMA

## database/schema.sql
```sql
-- ═══════════════════════════════════════════
-- Supabase Tabellen-Schema
-- Single Source of Truth für die Datenbankstruktur
-- ═══════════════════════════════════════════

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    added_date TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    cross_signal_tickers TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true
);

-- Kurzzeit-Gedächtnis (News-Stichpunkte pro Quartal)
CREATE TABLE IF NOT EXISTS short_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    bullet_points JSONB NOT NULL,
    sentiment_score FLOAT,
    category TEXT,
    quarter TEXT NOT NULL,
    is_material BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stm_ticker_quarter ON short_term_memory(ticker, quarter);

-- Langzeit-Gedächtnis (historische Earnings + KI-Performance)
CREATE TABLE IF NOT EXISTS long_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    eps_actual FLOAT,
    eps_consensus FLOAT,
    eps_whisper FLOAT,
    revenue_actual FLOAT,
    revenue_consensus FLOAT,
    stock_reaction_1d FLOAT,
    stock_reaction_5d FLOAT,
    ki_recommendation TEXT,
    ki_opportunity_score INT,
    ki_torpedo_score INT,
    outcome_correct BOOLEAN,
    key_learnings TEXT,
    guidance_direction TEXT,
    core_metric_name TEXT,
    core_metric_trend TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, quarter)
);

CREATE INDEX idx_ltm_ticker ON long_term_memory(ticker);

-- Makro-Snapshots
CREATE TABLE IF NOT EXISTS macro_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date TIMESTAMP NOT NULL,
    fed_rate FLOAT,
    fed_expectation TEXT,
    vix FLOAT,
    credit_spread_bps FLOAT,
    yield_curve TEXT,
    dxy FLOAT,
    regime TEXT,
    index_shorts_recommended BOOLEAN DEFAULT false,
    instrument_suggestions TEXT,
    geopolitical_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bitcoin-Snapshots
CREATE TABLE IF NOT EXISTS btc_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date TIMESTAMP NOT NULL,
    price FLOAT,
    price_7d_change_percent FLOAT,
    open_interest_usd FLOAT,
    open_interest_trend TEXT,
    funding_rate FLOAT,
    long_short_ratio FLOAT,
    liquidation_cluster_long FLOAT,
    liquidation_cluster_short FLOAT,
    dxy FLOAT,
    recommendation TEXT,
    reasoning TEXT,
    key_support FLOAT,
    key_resistance FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit-Reports (generierte Reports archiviert)
CREATE TABLE IF NOT EXISTS audit_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    report_date TIMESTAMP NOT NULL,
    earnings_date TIMESTAMP,
    opportunity_score FLOAT,
    torpedo_score FLOAT,
    recommendation TEXT,
    report_content TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reports_ticker_date ON audit_reports(ticker, report_date);
```

---

# TEIL 5: MODUL-README-TEMPLATES

## backend/app/data/README.md
```markdown
# Daten-Module

Jedes Modul in diesem Ordner verbindet sich mit einer externen API
und liefert Daten in den Pydantic-Schemas aus `schemas/`.

## Regeln
- Jedes Modul MUSS Mock-Daten unterstützen (config: use_mock_data)
- Jedes Modul nutzt den zentralen Rate-Limiter aus `backend/app/rate_limiter.py`
- Jedes Modul gibt Pydantic-Models zurück, keine rohen Dicts
- API-Keys kommen aus `backend/app/config.py`, nie hardcoded

## Module

| Datei | API | Schema | Beschreibung |
|-------|-----|--------|-------------|
| finnhub.py | Finnhub | earnings.*, sentiment.* | Earnings-Kalender, News, Short Interest, Insider |
| fmp.py | FMP | valuation.*, earnings.* | Fundamentaldaten, Analystenschätzungen, historische Earnings |
| fred.py | FRED | macro.* | VIX, Credit Spreads, Yield Curve, DXY, Fed Rate |
| coinglass.py | CoinGlass | macro.BitcoinSnapshot | Open Interest, Funding, Liquidation Cluster |
| sec_edgar.py | SEC EDGAR | sentiment.* | Form 8-K, Form 4 via RSS |
| yfinance_data.py | yfinance | technicals.* | Historische Kurse, technische Indikatoren |

## Mock-Daten
Fixture-Dateien liegen in `fixtures/[api_name]/`. Beispiel:
- `fixtures/finnhub/earnings_calendar.json`
- `fixtures/fmp/analyst_estimates_AAPL.json`
```

## backend/app/analysis/README.md
```markdown
# Analyse-Module

Module für KI-Analyse, Scoring und Report-Generierung.

## Regeln
- KI-Prompts werden aus `prompts/` geladen, NICHT hardcoded
- Scoring-Gewichtungen aus `config/scoring.yaml`, NICHT hardcoded
- Jede KI-Antwort wird geloggt (Prompt-Version, Input-Tokens, Output)

## Module

| Datei | Abhängigkeit | Beschreibung |
|-------|-------------|-------------|
| finbert.py | Lokales Modell | Sentiment-Score für Headlines (-1 bis +1) |
| deepseek.py | DeepSeek API | News-Zusammenfassung, Stichpunkt-Extraktion, Report-Generierung |
| groq.py | Groq API | Schnelle News-Extraktion (llama-3.1-8b-instant) |
| scoring.py | config/scoring.yaml, schemas/scores.py | Berechnet Opportunity + Torpedo Score |
| report_generator.py | Alle obigen Module | Generiert den vollständigen Audit-Report |

## Datenfluss
1. data/ Module liefern Rohdaten als Pydantic-Models
2. finbert.py filtert News-Headlines
3. groq.py extrahiert Stichpunkte aus relevanten News (schnell)
4. deepseek.py analysiert komplexe Daten und generiert Reports
5. scoring.py berechnet beide Scores aus allen Datenpunkten
6. report_generator.py kombiniert alles zum fertigen Report
```

## backend/app/memory/README.md
```markdown
# Gedächtnis-Module

CRUD-Operationen für das Kurzzeit- und Langzeit-Gedächtnis in Supabase.

## Module

| Datei | Tabelle | Beschreibung |
|-------|---------|-------------|
| short_term.py | short_term_memory | News-Stichpunkte pro Ticker pro Quartal |
| long_term.py | long_term_memory | Historische Earnings + KI-Performance |
| watchlist.py | watchlist | Watchlist-Verwaltung + Cross-Signal-Mappings |
| macro.py | macro_snapshots, btc_snapshots | Makro- und Bitcoin-Daten |

## Regeln
- Alle DB-Operationen über supabase-py Client aus `backend/app/db.py`
- Immer Pydantic-Models für Input und Output verwenden
- Archivierung: short_term → long_term nach Post-Earnings-Review
```

## backend/app/alerts/README.md
```markdown
# Alert-Module

Senden Benachrichtigungen per Telegram und E-Mail.

## Module

| Datei | Kanal | Beschreibung |
|-------|-------|-------------|
| telegram.py | Telegram Bot API | Push-Alerts: News, Torpedo-Warnungen, BTC-Alerts |
| email.py | SMTP via n8n | Sonntags-Report als formatierte HTML-E-Mail |

## Alert-Typen
- NEWS: Relevante Nachricht für Watchlist-Ticker
- TORPEDO: These-Killer erkannt (8-K, Insider-Sell, Downgrade)
- MACRO: Materielles Makro-Event (NFP, CPI, FOMC, Geopolitik)
- BITCOIN: Extreme Funding Rate, OI-Anomalie, Cluster-Annäherung
- REPORT: Sonntags-Report ist fertig (E-Mail)

## Schwellenwerte
Konfiguriert in `config/alerts.yaml` — nicht im Code ändern.
```

---

# TEIL 6: PROMPT-ARCHITEKTUR

## prompts/README.md
```markdown
# KI-Prompts

Jeder Prompt ist eine eigene Datei. Prompts sind auf Englisch formuliert
(bessere KI-Qualität). Output wird auf Deutsch angefordert.

## Versionierung
Jede Datei hat einen Header mit Version, Datum und Changelog.
Post-Earnings-Reviews dokumentieren, welche Prompt-Version verwendet wurde.

## Dateien

| Prompt | KI-Modell | Zweck |
|--------|-----------|-------|
| audit_report.md | Kimi K2.5 | Vollständiger Audit-Report für Earnings |
| news_extraction.md | DeepSeek | Stichpunkt-Extraktion aus Nachrichten |
| macro_header.md | DeepSeek | Wöchentlicher Makro-Regime-Header |
| btc_report.md | DeepSeek | Wöchentlicher Bitcoin-Lagebericht |
| post_earnings.md | DeepSeek | Post-Earnings-Review und Scoring-Vergleich |
| torpedo_alert.md | DeepSeek | Einordnung von Torpedo-Events |

## Format jeder Prompt-Datei
- YAML-Header: version, date, model, changelog
- SYSTEM: System-Prompt
- USER_TEMPLATE: User-Prompt mit {{platzhaltern}}
- EXPECTED_OUTPUT: Beschreibung des erwarteten Formats
```

---

# TEIL 7: INFRASTRUKTUR-DATEIEN

## docker-compose.yml
```yaml
version: "3.8"

services:
  backend:
    build: ./backend
    container_name: trading-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./config:/app/config:ro
      - ./prompts:/app/prompts:ro
      - ./fixtures:/app/fixtures:ro
    depends_on:
      - redis
    networks:
      - trading-net

  redis:
    image: redis:7-alpine
    container_name: trading-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - trading-net

  n8n:
    image: n8nio/n8n
    container_name: trading-n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    env_file:
      - .env
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD:-changeme}
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - trading-net

volumes:
  redis-data:
  n8n-data:

networks:
  trading-net:
    driver: bridge
```

## backend/Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System-Abhängigkeiten
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FinBERT-Modell vorladen (einmalig beim Build)
RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
    AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); \
    AutoTokenizer.from_pretrained('ProsusAI/finbert')"

# Anwendung
COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## backend/requirements.txt
```
# ═══════════════════════════════════════════
# Dependency-Whitelist
# Agenten: NUR diese Bibliotheken verwenden.
# Neue Dependency nötig? → In STATUS.md vermerken.
# ═══════════════════════════════════════════

# Web-Framework
fastapi==0.115.*
uvicorn==0.34.*

# HTTP-Client (für ALLE API-Calls)
httpx==0.28.*

# Daten-Validierung & Schemas
pydantic==2.10.*

# Datenbank
supabase==2.*

# KI / ML
transformers==4.47.*        # FinBERT
torch==2.5.*                # PyTorch für FinBERT (CPU)

# Finanzdaten
yfinance==0.2.*

# Config
pyyaml==6.*
python-dotenv==1.*

# Caching / Queue
redis==5.*

# Utilities
python-dateutil==2.*

# Logging
structlog==24.*

# Testing
pytest==8.*
pytest-asyncio==0.24.*
```

## .gitignore
```
# Secrets
.env

# Python
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/

# IDE
.vscode/
.idea/

# Docker
docker-compose.override.yml

# OS
.DS_Store
Thumbs.db

# Modelle (werden im Docker-Build geladen)
models/
*.bin
*.safetensors
```

---

# TEIL 8: FORTSCHRITTS-TRACKING

## STATUS.md
```markdown
# Projekt-Status

## Legende
- ⬜ TODO — Noch nicht begonnen
- 🔨 IN PROGRESS — Wird gerade bearbeitet
- ✅ DONE — Fertig implementiert
- 🧪 TESTED — Fertig und getestet

## Phase 1: Daten-Fundament

| Modul | Status | Notizen |
|-------|--------|---------|
| Supabase-Tabellen | ⬜ | |
| backend/app/config.py | ⬜ | |
| backend/app/db.py | ⬜ | |
| backend/app/rate_limiter.py | ⬜ | |
| backend/app/logger.py | ⬜ | |
| backend/app/data/finnhub.py | ⬜ | |
| backend/app/data/fmp.py | ⬜ | |
| backend/app/data/fred.py | ⬜ | |
| backend/app/data/yfinance_data.py | ⬜ | |
| backend/app/memory/watchlist.py | ⬜ | |
| fixtures/ Testdaten | ⬜ | |
| Docker-Compose lauffähig | ⬜ | |

## Phase 2: Audit-Report-Pipeline

| Modul | Status | Notizen |
|-------|--------|---------|
| backend/app/analysis/finbert.py | ⬜ | |
| backend/app/analysis/deepseek.py | ⬜ | |
| backend/app/analysis/kimi.py | ⬜ | |
| backend/app/analysis/scoring.py | ⬜ | |
| backend/app/analysis/report_generator.py | ⬜ | |
| prompts/audit_report.md | ⬜ | |
| prompts/macro_header.md | ⬜ | |
| backend/app/alerts/email.py | ⬜ | |
| n8n Sonntags-Workflow | ⬜ | |

## Phase 3: News-Pipeline & Alerts

| Modul | Status | Notizen |
|-------|--------|---------|
| backend/app/data/sec_edgar.py | ⬜ | |
| backend/app/memory/short_term.py | ⬜ | |
| backend/app/alerts/telegram.py | ⬜ | |
| prompts/news_extraction.md | ⬜ | |
| prompts/torpedo_alert.md | ⬜ | |
| n8n News-Check-Workflow | ⬜ | |
| n8n SEC-EDGAR-Workflow | ⬜ | |

## Phase 3b: Bitcoin-Modul

| Modul | Status | Notizen |
|-------|--------|---------|
| backend/app/data/coinglass.py | ⬜ | |
| prompts/btc_report.md | ⬜ | |
| BTC Telegram-Alerts | ⬜ | |

## Phase 4: Feedback-Loop

| Modul | Status | Notizen |
|-------|--------|---------|
| backend/app/memory/long_term.py | ⬜ | |
| prompts/post_earnings.md | ⬜ | |
| Performance-Auswertung | ⬜ | |

## Dependency-Requests
<!-- Hier vermerken Agenten, wenn sie eine neue Bibliothek brauchen -->
```

---

# TEIL 9: TASK-TEMPLATE FÜR AGENTEN

So formulieren wir Aufgaben für Antigravity-Agenten. Immer diese Struktur:

```
## Aufgabe: [Modulname] implementieren

**Lies zuerst:**
- `[Modul-Ordner]/README.md`
- `schemas/[relevantes_schema].py`
- `docs/apis/[api_name].md`
- `config/apis.yaml` → Abschnitt [api_name]

**Was zu tun ist:**
[Konkrete Beschreibung]

**Input:**
[Schema-Referenz]

**Output:**
[Schema-Referenz]

**Mock-Daten:**
Wenn `config/settings.yaml → use_mock_data: true`, lade aus `fixtures/[datei].json`

**Test:**
Erstelle `tests/test_[modul].py` mit Smoke-Test gegen Mock-Daten

**Wenn fertig:**
Update `STATUS.md` → Modul auf ✅ setzen
```

---

# TEIL 10: ERSTE SCHRITTE

## Reihenfolge zum Aufsetzen des Repositories

1. Repository auf GitHub erstellen: `antigravity-trading` (private)
2. CLAUDE.md im Root anlegen (aus Teil 1)
3. Komplette Ordnerstruktur anlegen lassen (Agenten-Task)
4. Config-Dateien anlegen (aus Teil 2)
5. Schema-Dateien anlegen (aus Teil 3)
6. .env.example und .gitignore anlegen (aus Teil 7)
7. docker-compose.yml und Dockerfile anlegen (aus Teil 7)
8. requirements.txt anlegen (aus Teil 7)
9. STATUS.md anlegen (aus Teil 8)
10. Alle README.md Dateien in den Modulordnern anlegen (aus Teil 5)
11. database/schema.sql anlegen (aus Teil 4)
12. Plattform-Spec als docs/SPEC.md einfügen

Danach: API-Dokumentationen in docs/apis/ sammeln. Erste Mock-Daten in fixtures/ ablegen. Dann Phase 1 starten.

## Erster Agenten-Task

```
Erstelle die komplette Verzeichnisstruktur für das Projekt.
Lies CLAUDE.md für die Struktur.
Lege alle Ordner an.
Lege in jedem Modulordner eine leere __init__.py an.
Lege alle README.md Dateien an (Inhalte aus docs/SPEC.md).
Lege alle Schema-Dateien an.
Lege alle Config-Dateien an.
Lege STATUS.md an.
Committe als "Initial project structure".
```
