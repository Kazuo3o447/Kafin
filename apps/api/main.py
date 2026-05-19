from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from pipeline.audit import load_audit_events
from pipeline.config import PlatformConfig
from pipeline.graph import run_pipeline
from data.sources.intelligence_adapter import build_filter_queue_entries


app = FastAPI(title="Trading Research Platform", version="0.1.0")


class RunRequest(BaseModel):
    ticker: str
    phase: int | None = None


class WatchlistRequest(BaseModel):
    note: str | None = None


@app.post("/api/agents/run")
def start_agent_run(request: RunRequest) -> dict[str, Any]:
    config = PlatformConfig.from_env(phase=request.phase)
    state = run_pipeline(request.ticker, config=config)
    return state


@app.get("/api/agents/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    events = load_audit_events(run_id, Path(os.getenv("AUDIT_DIR", "audit")))
    if not events:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run_id, "events": events, "latest_status": events[-1]["event_type"]}


@app.get("/api/agents/runs/{run_id}/audit")
def get_run_audit(run_id: str) -> list[dict[str, Any]]:
    return load_audit_events(run_id, Path(os.getenv("AUDIT_DIR", "audit")))


@app.post("/api/agents/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, str]:
    return {"run_id": run_id, "status": "not_supported_for_local_synchronous_runs"}


@app.get("/api/lessons/active")
def list_active_lessons() -> list[dict[str, str]]:
    lesson_dir = Path("research/lessons/active")
    return [{"id": path.stem, "body": path.read_text(encoding="utf-8")} for path in lesson_dir.glob("*.md")]


@app.post("/api/lessons/propose")
def propose_lesson(payload: dict[str, Any]) -> dict[str, str]:
    title = str(payload.get("title", "untitled")).strip() or "untitled"
    body = str(payload.get("body", "")).strip()
    if not body:
        raise HTTPException(status_code=400, detail="body is required")
    target = Path("research/lessons/proposed") / f"{_slug(title)}.md"
    target.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return {"status": "proposed", "path": str(target)}


@app.post("/api/lessons/{lesson_id}/accept")
def accept_lesson(lesson_id: str) -> dict[str, str]:
    source = Path("research/lessons/proposed") / f"{lesson_id}.md"
    if not source.exists():
        raise HTTPException(status_code=404, detail="lesson proposal not found")
    target = Path("research/lessons/active") / source.name
    source.replace(target)
    return {"status": "active", "path": str(target)}


@app.post("/api/lessons/{lesson_id}/retire")
def retire_lesson(lesson_id: str) -> dict[str, str]:
    source = Path("research/lessons/active") / f"{lesson_id}.md"
    if not source.exists():
        raise HTTPException(status_code=404, detail="active lesson not found")
    target = Path("research/lessons/retired") / source.name
    source.replace(target)
    return {"status": "retired", "path": str(target)}


@app.get("/api/prompts")
def list_prompts() -> list[str]:
    return [str(path) for path in Path("agents").glob("*/prompt.md")]


@app.get("/api/prompts/proposed")
def list_proposed_prompts() -> list[str]:
    return [str(path) for path in Path("prompts/proposed").glob("*.md")]


@app.post("/api/prompts/{prompt_id}/accept")
def accept_prompt(prompt_id: str) -> dict[str, str]:
    return {"prompt_id": prompt_id, "status": "manual_review_required"}


@app.get("/api/calibration/scores")
def get_score_weights() -> dict[str, Any]:
    path = Path("calibration/current_weights.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="current weights missing")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/calibration/proposed")
def list_proposed_calibration() -> list[str]:
    return [str(path) for path in Path("calibration/proposed").glob("*.json")]


@app.post("/api/calibration/{proposal_id}/accept")
def accept_calibration(proposal_id: str) -> dict[str, str]:
    return {"proposal_id": proposal_id, "status": "manual_review_required"}


@app.get("/api/health/model")
def model_health() -> dict[str, Any]:
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"status": "misconfigured", "detail": "DEEPSEEK_API_KEY missing"}
    try:
        request = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return {"status": "ok", "raw": response.read().decode("utf-8")}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "unavailable", "detail": str(exc)}


@app.get("/api/health/data")
def data_health() -> dict[str, Any]:
    snapshot_count = len(list(Path("data/snapshots").glob("*.json")))
    return {"status": "ok", "snapshot_count": snapshot_count}


@app.post("/api/research/documents/upload")
async def upload_research_document(file: UploadFile = File(...)) -> dict[str, str]:
    target = _safe_path(Path("research/inbox"), file.filename)
    content = await file.read()
    target.write_bytes(content)
    return {"status": "uploaded", "path": str(target)}


@app.get("/api/research/documents")
def list_research_documents() -> list[dict[str, str]]:
    documents = []
    for directory in [Path("research/inbox"), Path("research/processed"), Path("research/rejected")]:
        for path in directory.glob("*"):
            if path.is_file():
                documents.append({"id": path.name, "path": str(path), "bucket": directory.name})
    return documents


@app.get("/api/research/documents/{document_id}")
def get_research_document(document_id: str) -> dict[str, str]:
    path = _find_research_file(document_id, ["inbox", "processed", "rejected"])
    return {"id": path.name, "path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")}


@app.post("/api/research/documents/{document_id}/process")
def process_research_document(document_id: str) -> dict[str, str]:
    source = _find_research_file(document_id, ["inbox"])
    target = _safe_path(Path("research/processed"), source.name)
    source.replace(target)
    summary = target.with_suffix(target.suffix + ".summary.md")
    summary.write_text(
        f"# Summary: {target.name}\n\nStatus: processed placeholder. Full extraction is Phase 1 work.\n",
        encoding="utf-8",
    )
    return {"status": "processed", "path": str(target), "summary": str(summary)}


@app.get("/api/research/documents/{document_id}/chunks")
def get_document_chunks(document_id: str) -> list[dict[str, str]]:
    path = _find_research_file(document_id, ["processed"])
    text = path.read_text(encoding="utf-8", errors="replace")
    return [{"chunk_id": str(index), "text": text[index : index + 2000]} for index in range(0, len(text), 2000)]


@app.get("/api/research/documents/{document_id}/summary")
def get_document_summary(document_id: str) -> dict[str, str]:
    path = _find_research_file(document_id, ["processed"])
    summary = path.with_suffix(path.suffix + ".summary.md")
    if not summary.exists():
        raise HTTPException(status_code=404, detail="summary not found")
    return {"id": document_id, "summary": summary.read_text(encoding="utf-8")}


@app.get("/api/research/frameworks")
def list_frameworks() -> list[dict[str, Any]]:
    frameworks = []
    for path in Path("research/frameworks").glob("*.json"):
        frameworks.append(json.loads(path.read_text(encoding="utf-8")))
    return frameworks


@app.post("/api/research/frameworks/extract/{document_id}")
def extract_frameworks(document_id: str) -> dict[str, str]:
    _find_research_file(document_id, ["processed"])
    target = Path("research/frameworks") / f"{_slug(document_id)}_framework.json"
    payload = {
        "framework_name": "placeholder",
        "source_document": document_id,
        "confidence": "low",
        "limitations": ["manual review required"],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "extracted_placeholder", "path": str(target)}


@app.get("/api/research/frameworks/{framework_id}")
def get_framework(framework_id: str) -> dict[str, Any]:
    path = _safe_path(Path("research/frameworks"), f"{framework_id}.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="framework not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/api/research/frameworks/{framework_id}")
def update_framework(framework_id: str, payload: dict[str, Any]) -> dict[str, str]:
    path = _safe_path(Path("research/frameworks"), f"{framework_id}.json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "updated", "path": str(path)}


@app.post("/api/research/companies/{ticker}/run")
def run_company_research(ticker: str) -> dict[str, Any]:
    return run_pipeline(ticker, PlatformConfig.from_env(phase=1))


@app.get("/api/research/companies/{ticker}/card")
def get_company_card(ticker: str) -> dict[str, Any]:
    path = _latest_card_json(ticker)
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/research/companies/{ticker}/metrics")
def get_company_metrics(ticker: str) -> dict[str, Any]:
    path = _safe_path(Path("data/snapshots"), f"{ticker.upper()}.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="snapshot not found")
    return json.loads(path.read_text(encoding="utf-8")).get("metrics", {})


@app.get("/api/research/companies/{ticker}/score")
def get_company_score(ticker: str) -> dict[str, Any]:
    card = json.loads(_latest_card_json(ticker).read_text(encoding="utf-8"))
    return {
        "ticker": ticker.upper(),
        "growth_research_score": card.get("growth_research_score"),
        "score_breakdown": card.get("score_breakdown", {}),
        "gate": card.get("gate"),
    }


@app.post("/api/research/companies/{ticker}/red-team")
def run_company_redteam(ticker: str) -> dict[str, str]:
    card = _latest_card_json(ticker)
    redteam = Path("research/cards") / f"{card.stem}_redteam_requested.json"
    redteam.write_text(
        json.dumps({"ticker": ticker.upper(), "status": "manual_redteam_request_logged"}, indent=2),
        encoding="utf-8",
    )
    return {"status": "queued_placeholder", "path": str(redteam)}


@app.post("/api/research/companies/{ticker}/handoff-to-screener")
def handoff_to_screener(ticker: str) -> dict[str, Any]:
    return run_pipeline(ticker, PlatformConfig.from_env(phase=1)).get("screener", {})


@app.get("/api/research/watchlist")
def get_watchlist() -> list[dict[str, Any]]:
    return _read_watchlist()


@app.post("/api/research/watchlist/{ticker}")
def add_to_watchlist(ticker: str, request: WatchlistRequest | None = None) -> list[dict[str, Any]]:
    watchlist = _read_watchlist()
    entry = {"ticker": ticker.upper(), "note": request.note if request else None}
    if not any(item["ticker"] == entry["ticker"] for item in watchlist):
        watchlist.append(entry)
    _write_watchlist(watchlist)
    return watchlist


@app.delete("/api/research/watchlist/{ticker}")
def delete_from_watchlist(ticker: str) -> list[dict[str, Any]]:
    watchlist = [item for item in _read_watchlist() if item["ticker"] != ticker.upper()]
    _write_watchlist(watchlist)
    return watchlist


@app.get("/api/research/watchlist/export")
def export_watchlist() -> dict[str, Any]:
    return {"watchlist": _read_watchlist()}


@app.post("/api/research/watchlist/filter-sync")
def sync_watchlist_filter_queue() -> dict[str, Any]:
    watchlist = _read_watchlist()
    snapshots = {
        item["ticker"]: _read_snapshot_payload(item["ticker"])
        for item in watchlist
        if _snapshot_path(item["ticker"]).exists()
    }
    market_snapshot = _read_market_snapshot()
    queue = build_filter_queue_entries(watchlist, snapshots, market_snapshot)
    path = Path("research/filter_queue.json")
    path.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return {"status": "synced", "count": len(queue), "path": str(path), "queue": queue}


@app.get("/api/research/audit/{job_id}")
def get_research_audit(job_id: str) -> list[dict[str, Any]]:
    return load_audit_events(job_id, Path(os.getenv("AUDIT_DIR", "audit")))


@app.get("/api/research/news/company/{ticker}")
def get_company_news(ticker: str) -> dict[str, Any]:
    snapshot = _read_snapshot_payload(ticker)
    return {"ticker": ticker.upper(), "news": snapshot.get("news", {}).get("company", [])}


@app.get("/api/research/news/market")
def get_market_news() -> dict[str, Any]:
    snapshot = _read_market_snapshot()
    return {"news": snapshot.get("news", [])}


@app.get("/api/research/sentiment/company/{ticker}")
def get_company_sentiment(ticker: str) -> dict[str, Any]:
    snapshot = _read_snapshot_payload(ticker)
    return {"ticker": ticker.upper(), "sentiment": snapshot.get("sentiment", {}).get("company", {})}


@app.get("/api/research/sentiment/market")
def get_market_sentiment() -> dict[str, Any]:
    snapshot = _read_market_snapshot()
    return {"sentiment": snapshot.get("sentiment", {})}


@app.get("/api/research/sources/{source_id}")
def get_research_source(source_id: str) -> dict[str, str]:
    path = _find_research_file(source_id, ["evidence", "processed", "inbox"])
    return {"id": path.name, "content": path.read_text(encoding="utf-8", errors="replace")}


@app.get("/api/research/evidence/{evidence_id}")
def get_research_evidence(evidence_id: str) -> dict[str, str]:
    path = _safe_path(Path("research/evidence"), evidence_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="evidence not found")
    return {"id": path.name, "content": path.read_text(encoding="utf-8", errors="replace")}


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _safe_path(directory: Path, name: str) -> Path:
    candidate = directory / Path(name).name
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _find_research_file(name: str, buckets: list[str]) -> Path:
    for bucket in buckets:
        path = _safe_path(Path("research") / bucket, name)
        if path.exists():
            return path
    raise HTTPException(status_code=404, detail="file not found")


def _latest_card_json(ticker: str) -> Path:
    matches = sorted(Path("research/cards").glob(f"{ticker.upper()}_*.json"), reverse=True)
    matches = [path for path in matches if "_redteam" not in path.stem]
    if not matches:
        raise HTTPException(status_code=404, detail="card not found")
    return matches[0]


def _read_watchlist() -> list[dict[str, Any]]:
    path = Path("research/watchlist.json")
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_watchlist(watchlist: list[dict[str, Any]]) -> None:
    path = Path("research/watchlist.json")
    path.write_text(json.dumps(watchlist, indent=2, sort_keys=True), encoding="utf-8")


def _snapshot_path(ticker: str) -> Path:
    return _safe_path(Path("data/snapshots"), f"{ticker.upper()}.json")


def _read_snapshot_payload(ticker: str) -> dict[str, Any]:
    path = _snapshot_path(ticker)
    if not path.exists():
        raise HTTPException(status_code=404, detail="snapshot not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_market_snapshot() -> dict[str, Any]:
    path = _safe_path(Path("data/snapshots"), "_MARKET.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="market snapshot not found")
    return json.loads(path.read_text(encoding="utf-8"))
