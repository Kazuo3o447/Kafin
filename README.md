# Trading Research Platform

Lokale Trading-Research-Plattform mit klaren Guardrails: keine Broker-API, keine Orderausfuehrung, keine autonomen Kauf- oder Verkaufssignale. Der aktuelle Code liefert einen auditierbaren Research-Workflow mit FastAPI, Streamlit-Frontend, JSONL-Audit-Trail und dateibasierten Research-Artefakten.

## Aktueller Stand

- Phase 0 ist lauffaehig als Smoke-Test mit Audit-Events.
- Phase 1 laeuft ueber lokale Snapshots in `data/snapshots/` und endet nach Research Card, Red-Team und Screener.
- Phase 2+-Bausteine wie Risk Engine und Execution Gatekeeper sind vorhanden, aber nicht der Standardpfad.
- Postgres, pgvector und Redis sind als Infrastruktur vorbereitet; der aktuelle Standardpfad arbeitet lokal zuerst mit Dateien.

## Schnellstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item .env.example .env
python -m pipeline.run NVDA --phase 0
python -m pytest
```

Fuer qualitative LLM-Research mit DeepSeek:

```powershell
$env:DEEPSEEK_API_KEY = "<key>"
$env:ALLOW_LLM = "true"
python -m pipeline.run NVDA --phase 1
```

## Lokale Oberflaechen

API lokal starten:

```powershell
uvicorn apps.api.main:app --reload --port 8000
```

Frontend lokal starten:

```powershell
streamlit run apps/frontend/app.py
```

Danach erreichbar:

- API/OpenAPI: `http://localhost:8000/docs`
- Frontend: `http://localhost:8501`

## Docker Compose

```powershell
docker compose up --build postgres redis api frontend
```

Enthalten sind:

- `postgres` mit `pgvector`
- `redis`
- `api` auf Port `8000`
- `frontend` auf Port `8501`

## Wichtige Befehle

```powershell
python -m pipeline.run NVDA --phase 0
python -m pipeline.run NVDA --phase 1
platform-run NVDA --phase 1
platform-replay <run_id>
python scripts/check_forbidden_imports.py
python -m pytest
```

## Pipeline-Verhalten

### Phase 0

- erzeugt einen minimalen Smoke-Test-Lauf
- schreibt Audit-Events
- erzeugt keine echte Research Card aus Marktdaten

### Phase 1

- laedt `data/snapshots/<TICKER>.json`
- prueft Pflichtfelder
- schreibt bei fehlenden Pflichtfeldern eine Ablehnung nach `research/rejected/`
- erzeugt bei gueltigen Daten eine Research Card in `research/cards/`
- fuehrt Red-Team und Screener aus
- endet ohne Risk Engine, Execution Gatekeeper oder Paper-Trade-Simulation

### Phase 2+

- kann Risk Engine und Execution Gatekeeper aktivieren
- ist im Repository angelegt, aber noch nicht der Standard-Workflow

## Wichtige Artefakte

- Audit-Events: `audit/<YYYY-MM>/<run_id>.jsonl`
- Research Cards: `research/cards/`
- Rejections: `research/rejected/`
- Journal: `journal/YYYY-MM-DD.md`
- Frontend-Logs: `logs/frontend/YYYY-MM-DD.jsonl`
- Gewichte: `calibration/current_weights.json`

## API-Ueberblick

Die FastAPI-App deckt aktuell vier Bereiche ab:

- Agent Runs und Audit
- Lessons, Prompts und Calibration
- Health-Checks fuer Modell- und Datenstatus
- Research-Endpunkte fuer Dokumente, Frameworks, Watchlist, News, Sentiment, Cards und Screener-Handoff

Die OpenAPI-Dokumentation ist unter `http://localhost:8000/docs` verfuegbar.

## Frontend-Ueberblick

Das Streamlit-Frontend in `apps/frontend/app.py` bietet aktuell diese Seiten:

- `Ops Desk`
- `Full Audit`
- `Watchlist`
- `Audit Terminal`
- `App Logs`
- `Approval Queue`
- `Knowledge Base`
- `Admin`

Der Fokus liegt auf lokaler Bedienung, Auditierbarkeit und Human-in-the-loop, nicht auf Trading-Automation.

## Wichtige Umgebungsvariablen

```text
PLATFORM_PHASE=0
DEEPSEEK_API_KEY=
ALLOW_LLM=false
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
AUDIT_DIR=audit
DATABASE_URL=postgresql://platform:platform@postgres:5432/platform
REDIS_URL=redis://redis:6379/0
```

Weitere optionale Provider-Keys stehen in `.env.example`.

## Guardrails

- keine Broker- oder Exchange-Integrationen
- keine autonome Orderausfuehrung
- Phase-Gating im Pipeline-Code
- dateibasierter Audit-Trail fuer jeden Lauf
- verbotene Trading-Imports werden ueber `scripts/check_forbidden_imports.py` geprueft
