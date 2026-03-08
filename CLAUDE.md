# Kafin — KI-gestützte Earnings-Trading-Plattform

## Was ist Kafin?
Eine Plattform, die Finanzdaten sammelt, mit einer KI-Kaskade analysiert und wöchentliche Audit-Reports mit Handlungsempfehlungen für Aktien-Earnings und Bitcoin generiert. Der Trader entscheidet — Kafin empfiehlt.

## Architektur
- Backend: Python FastAPI auf NUC (ZimaOS + Docker)
- Datenbank: Supabase (gehostetes PostgreSQL)
- Frontend: Next.js auf Vercel (spätere Phase)
- KI: FinBERT (lokal) → DeepSeek API → Kimi K2.5 API → Frontier-Fallback
- Alerts: Telegram Bot + E-Mail via n8n
- Bitcoin: CoinGlass API für Derivate-Daten

## Regeln für Agenten

### Bevor du arbeitest
1. Lies die README.md im Modulordner, an dem du arbeitest
2. Lies die relevanten Schemas in schemas/
3. Lies die API-Docs in docs/apis/ wenn du eine externe API nutzt
4. Prüfe STATUS.md ob abhängige Module fertig sind

### Code-Konventionen
- Python 3.11+, Type Hints überall
- Naming: snake_case für Variablen/Funktionen, PascalCase für Klassen
- Kommentare und Docs: Deutsch
- Code und Variablen: Englisch
- HTTP-Client: httpx (nicht requests, nicht aiohttp)
- Schemas: Pydantic v2 Models aus schemas/
- Datenbank: supabase-py Client aus backend/app/db.py
- Config: Alles aus config/ laden, nie hardcoden
- Secrets: Aus Environment-Variablen via backend/app/config.py, NIE im Code
- Nutze NUR Bibliotheken aus requirements.txt

### Datei-Header
Jede .py-Datei beginnt mit:
"""
[Modulname] — [Kurzbeschreibung]

Input:  [Was kommt rein? Welches Schema?]
Output: [Was kommt raus? Welches Schema?]
Deps:   [Welche anderen Module werden genutzt?]
Config: [Welche Config-Werte werden gelesen?]
API:    [Welche externe API? Oder "Keine"]
"""

### Error-Handling
- Jeder externe API-Call in try/except
- Bei Fehler: logger.error() mit Kontext (API, Ticker, Endpoint)
- Rate-Limit-Fehler: Retry mit Backoff via zentralen Rate-Limiter
- Fehlende Daten: None zurückgeben + loggen, nie stilles Verschlucken

### Mock-Daten
- Prüfe config/settings.yaml → use_mock_data: true/false
- Wenn true: Lade aus fixtures/ statt echte API-Calls
- Jedes Daten-Modul MUSS beide Pfade unterstützen

### Tests
- Jedes Modul bekommt test_[modul].py
- Mindestens ein Smoke-Test gegen Mock-Daten
- Tests nutzen IMMER Mock-Daten

## Verzeichnisstruktur
docs/           → Spezifikation, API-Docs
config/         → YAML-Dateien für konfigurierbare Werte
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
