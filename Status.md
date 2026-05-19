# Projektstatus

**Stand:** 2026-05-19  
**Projekt:** Private Trading-Research-Plattform Kafin  
**Status:** lauffaehiges lokales Research-System mit Phase-0-Smoke-Test, dateibasierter Phase-1-Pipeline, FastAPI und Streamlit  
**Leitplanke:** Keine Broker-API, keine autonome Orderausfuehrung, keine Kaufempfehlungen.

---

## 1. Kurzfassung

Das Repository ist nicht mehr nur ein loses Skelett. Der aktuelle Code deckt einen vollstaendigen lokalen Arbeitsfluss ab:

- Pipeline-Lauf per CLI oder API
- JSONL-Audit fuer jeden Lauf
- Research Card und Red-Team-Artefakte auf Dateibasis
- deterministischer Screener in Phase 1
- Streamlit-Oberflaeche fuer Ops, Audit, Watchlist, Knowledge Base und Admin
- FastAPI-Endpunkte fuer Runs, Research, Watchlist, Dokumente, Lessons, Calibration und Health

Der Standardpfad bleibt konservativ:

- `PLATFORM_PHASE=0` als sicherer Smoke-Test
- Phase 1 endet nach Research, Red-Team und Screener
- Risk Engine und Execution Gatekeeper sind nur fuer `phase >= 2` vorgesehen
- keine Broker- oder Exchange-Integration im Codepfad

---

## 2. Laufbare Komponenten

### CLI

- `python -m pipeline.run <TICKER> --phase <N>`
- `platform-run <TICKER> --phase <N>`
- `platform-replay <run_id>`

### API

- FastAPI-App in `apps/api/main.py`
- lokale Standard-URL bei manuellem Start: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`

### Frontend

- Streamlit-App in `apps/frontend/app.py`
- lokale Standard-URL: `http://localhost:8501`

### Docker Compose

`docker-compose.yml` startet:

- `postgres` mit `pgvector`
- `redis`
- `api`
- `frontend`

---

## 3. Pipeline-Ist-Zustand

Die zentrale Ausfuehrung liegt in `pipeline/graph.py`.

### Phase 0

- erstellt einen minimalen Pipeline-State
- schreibt Audit-Events
- erzeugt eine Dummy-Card
- endet mit `research_complete`

### Phase 1

- laedt `data/snapshots/<TICKER>.json`
- prueft Pflichtfelder
- schreibt bei fehlenden Feldern eine Ablehnung nach `research/rejected/`
- erzeugt eine Research Card
- fuehrt den Red-Team-Agenten aus
- fuehrt den deterministischen Screener aus
- schreibt einen Journal-Eintrag, dass kein Trade simuliert wurde

### Phase 2+

- aktiviert optional Risk Engine und Execution Gatekeeper
- ist technisch angelegt, aber nicht der Default-Modus

Wichtige Eigenschaft des aktuellen Codes:

- der produktive Pfad ist eine einfache, lokale Python-Orchestrierung
- `pipeline/langgraph_builder.py` und `pipeline/checkpointer.py` sind vorbereitende Bausteine, aber nicht der aktuelle Standardpfad

---

## 4. Agenten und Worker

### Research Agent

- Pfad: `agents/research/`
- schreibt Markdown- und JSON-Cards nach `research/cards/`
- kann deterministisch laufen oder LLM-Nutzung aktivieren, wenn `ALLOW_LLM=true` gesetzt ist

### Red-Team Agent

- Pfad: `agents/redteam/`
- erzeugt Red-Team-Artefakte zu bestehenden Cards

### Journal Agent

- Pfad: `agents/journal/`
- schreibt faktenbasierte Eintraege nach `journal/YYYY-MM-DD.md`

### Review Agent

- aktuell als Prompt/Workflow-Vorlage in `agents/review/`
- noch kein autonomer Produktionsschritt

### Daten-Worker

- Adapter und Datenquellen liegen unter `data/sources/`
- Worker-Verzeichnisse unter `workers/` sind vorbereitet, aber noch nicht als vollstaendige automatische Pipeline verdrahtet

---

## 5. API-Oberflaeche

Die FastAPI-App bietet aktuell diese Gruppen:

### Agent Runs

- `POST /api/agents/run`
- `GET /api/agents/runs/{run_id}`
- `GET /api/agents/runs/{run_id}/audit`
- `POST /api/agents/runs/{run_id}/cancel`

### Lessons, Prompts, Calibration

- aktive Lessons auflisten, vorschlagen, akzeptieren, retiren
- aktive und vorgeschlagene Prompts auflisten
- aktuelle und vorgeschlagene Calibration-Dateien auflisten

### Health

- `GET /api/health/model`
- `GET /api/health/data`

### Research

- Dokumente uploaden, listen, lesen, verarbeiten, splitten und zusammenfassen
- Framework-Dateien extrahieren, lesen und aktualisieren
- Company Research starten sowie Card, Metriken, Score und Screener-Handoff abrufen
- Watchlist lesen, erweitern, loeschen, exportieren und in `research/filter_queue.json` synchronisieren
- News-, Sentiment-, Audit-, Source- und Evidence-Endpunkte

Ein Teil der Research-Endpunkte ist bewusst als Platzhalter oder Minimalimplementierung angelegt, bis PDF-Parsing, Embeddings und vollstaendige Datenanreicherung nachgezogen sind.

---

## 6. Frontend-Ist-Zustand

Die Streamlit-App ist kein reiner Demo-Screen mehr. Die aktuell verdrahteten Seiten sind:

- `Ops Desk`
- `Full Audit`
- `Watchlist`
- `Audit Terminal`
- `App Logs`
- `Approval Queue`
- `Knowledge Base`
- `Admin`

Wichtige Merkmale:

- kompakter Ops-/Research-Desk statt Marketing-UI
- lokale Frontend-Logs unter `logs/frontend/`
- Karten-, Snapshot- und Audit-Ansichten in einer App
- Human-in-the-loop-Oberflaechen ohne Orderlogik

Die Approval Queue ist aktuell eine vorsichtige UI-Schicht. Sie ist keine Orderfreigabe und ersetzt keine Phase-2-Gates.

---

## 7. Persistenz und Artefakte

Aktuell ist der dateibasierte Pfad zentral:

- Audit: `audit/<YYYY-MM>/<run_id>.jsonl`
- Cards: `research/cards/`
- Ablehnungen: `research/rejected/`
- Journal: `journal/`
- Frontend-Logs: `logs/frontend/`
- Filter-Queue: `research/filter_queue.json`
- Gewichte: `calibration/current_weights.json`

Parallel dazu existiert ein SQL-Schema in `data/schema/001_init.sql` fuer Postgres/pgvector. Dieses Schema ist Infrastrukturgrundlage, aber nicht der einzige aktuelle Persistenzpfad.

---

## 8. Guardrails

Die Sicherheitsgrenzen sind im Repository explizit sichtbar:

- keine Broker-API im Code
- keine Ordererzeugung im Backend
- keine autonome Freigabe im Frontend
- Phase-Gating im Pipeline-Code
- verbotene Trading-Imports werden durch `scripts/check_forbidden_imports.py` gesucht

Der wichtigste funktionale Guardrail ist weiterhin: Phase 1 endet nach Research, Red-Team und Screener.

---

## 9. Bekannte Grenzen

Der aktuelle Stand ist brauchbar, aber noch kein vollstaendiges Phase-1-Zielbild.

- Nicht alle Datenadapter liefern bereits vollstaendige Pflichtfeld-Snapshots.
- Dokumenten-Ingestion ist API-seitig vorhanden, aber noch nicht als vollwertiger Extraktionspfad umgesetzt.
- Embeddings, pgvector-Nutzung und LangGraph-Checkpointing sind vorbereitet, aber nicht Leitpfad des aktuellen Runs.
- FinBERT-, RSS- und Markt-/Unternehmens-Sentiment sind im Datenmodell und in den Endpunkten angelegt, aber noch nicht durchgaengig automatisiert.
- Outcome-Tagging, Reviews und Lessons-Lernschleife sind strukturell vorhanden, aber noch nicht als kompletter Produktionsprozess verdrahtet.

---

## 10. Naechster sinnvoller Fokus

Der naechste technische Meilenstein ist nicht weiteres UI-Scaffolding, sondern sauberer Phase-1-Durchsatz:

1. Snapshots fuer die Pflichtfelder stabilisieren.
2. Research- und Red-Team-Laeufe mit realen Evidenzen anreichern.
3. News-, Sentiment- und Filter-Queue-Pfad voll verdrahten.
4. Dokumenten-Ingestion vom Platzhalter zur belastbaren Extraktion ausbauen.
5. Lessons, Reviews und Outcome-Tagging in den realen Workflow ziehen.

