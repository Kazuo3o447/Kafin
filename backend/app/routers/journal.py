"""
journal.py — Trade-Journal CRUD
Routen: GET/POST /api/journal, PUT/DELETE /api/journal/{id}
P&L wird serverseitig berechnet (direction-aware).
Tabelle: trade_journal (erstellt via init_db.py)

Endpoints:
  GET  /api/journal          → alle Einträge (neueste zuerst)
  POST /api/journal          → neuer Eintrag
  PUT  /api/journal/{id}     → Eintrag aktualisieren (z.B. Exit eintragen)
  DELETE /api/journal/{id}   → Eintrag löschen
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime, timezone
from backend.app.database import get_supabase_client
from backend.app.logger import get_logger
from backend.app.cache import cache_get

logger = get_logger(__name__)
router = APIRouter(tags=["journal"])


class JournalEntryCreate(BaseModel):
    ticker: str
    direction: str = "long"
    entry_date: date
    entry_price: float
    shares: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    thesis: Optional[str] = None
    opportunity_score: Optional[float] = None
    torpedo_score: Optional[float] = None
    recommendation: Optional[str] = None
    notes: Optional[str] = None


class JournalEntryUpdate(BaseModel):
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    notes: Optional[str] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    thesis: Optional[str] = None


@router.get("/api/journal")
async def get_journal(ticker: Optional[str] = None, limit: int = 100):
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=503, detail="DB nicht verfügbar")
    try:
        q = db.table("trade_journal").select("*").order("entry_date", desc=True).limit(limit)
        if ticker:
            q = q.eq("ticker", ticker.upper())
        result = await q.execute_async()
        entries = result.data or []

        # P&L berechnen für geschlossene Trades
        for e in entries:
            ep = e.get("entry_price")
            xp = e.get("exit_price")
            sh = e.get("shares")
            if ep and xp and sh:
                direction = e.get("direction", "long")
                mult = 1 if direction == "long" else -1
                pnl = mult * (xp - ep) * sh
                pnl_pct = mult * ((xp - ep) / ep) * 100
                e["pnl"] = round(pnl, 2)
                e["pnl_pct"] = round(pnl_pct, 2)
            else:
                e["pnl"] = None
                e["pnl_pct"] = None

        # Aktive Signale für offene Positionen aus Cache
        try:
            feed_cache = await cache_get("signals:feed")
            signal_map: dict[str, list] = {}
            if feed_cache:
                for sig in (feed_cache.get("signals") or []):
                    t = (sig.get("ticker") or "").upper()
                    if t not in signal_map:
                        signal_map[t] = []
                    signal_map[t].append({
                        "signal_type": sig.get("signal_type"),
                        "priority":    sig.get("priority"),
                        "headline":    sig.get("headline"),
                    })
            # An offene Positionen anhängen
            for e in entries:
                if e.get("exit_date") is None:
                    t = (e.get("ticker") or "").upper()
                    e["active_signals"] = signal_map.get(t, [])
                else:
                    e["active_signals"] = []
        except Exception as ex:
            logger.warning(f"Signal cache for journal: {ex}")
            for e in entries:
                e["active_signals"] = []

        return {"entries": entries, "total": len(entries)}
    except Exception as ex:
        logger.error(f"Journal GET fehler: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/api/journal")
async def create_journal_entry(body: JournalEntryCreate):
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=503, detail="DB nicht verfügbar")
    try:
        record = body.model_dump()
        record["ticker"] = record["ticker"].upper()
        record["entry_date"] = str(record["entry_date"])
        result = await db.table("trade_journal").insert(record).execute_async()
        return {"success": True, "entry": (result.data or [{}])[0]}
    except Exception as ex:
        logger.error(f"Journal POST fehler: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


@router.put("/api/journal/{entry_id}")
async def update_journal_entry(entry_id: int, body: JournalEntryUpdate):
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=503, detail="DB nicht verfügbar")
    try:
        update = {k: v for k, v in body.model_dump().items() if v is not None}
        if "exit_date" in update:
            update["exit_date"] = str(update["exit_date"])
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.table("trade_journal").update(update).eq("id", entry_id).execute_async()
        if not result.data:
            raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
        return {"success": True, "entry": result.data[0]}
    except HTTPException:
        raise
    except Exception as ex:
        logger.error(f"Journal PUT fehler: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


@router.delete("/api/journal/{entry_id}")
async def delete_journal_entry(entry_id: int):
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=503, detail="DB nicht verfügbar")
    try:
        await db.table("trade_journal").delete().eq("id", entry_id).execute_async()
        return {"success": True}
    except Exception as ex:
        logger.error(f"Journal DELETE fehler: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))
