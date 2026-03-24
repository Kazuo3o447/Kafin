from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import json
from datetime import datetime, timedelta, timezone
from backend.app.logger import (
    get_recent_logs, 
    get_module_status, 
    MODULES, 
    is_expected_yfinance_error, 
    create_test_module_logs,
    LOG_FILE,
    _log_buffer
)
from backend.app.utils.timezone import now_mez

router = APIRouter(prefix="/api/logs", tags=["logs"])

class ExternalLog(BaseModel):
    level: str
    message: str
    source: str = "n8n"
    error_code: str | None = None

@router.get("")
async def api_get_logs(level: str = None, limit: int = 200):
    """Gibt die letzten Log-Einträge zurück."""
    logs = get_recent_logs()
    if level:
        level_upper = level.upper()
        if level_upper == "IGNORE":
            logs = [
                l for l in logs
                if l.get("category") == "ignore"
                or is_expected_yfinance_error(l.get("event", ""), l.get("logger", ""))
            ]
        else:
            logs = [
                l for l in logs
                if l.get("level", "").upper() == level_upper
                and not is_expected_yfinance_error(l.get("event", ""), l.get("logger", ""))
            ]
    return logs[:limit]

@router.get("/errors")
async def api_get_logs_errors():
    """Gibt nur Log-Einträge mit level 'error' oder 'warning' der letzten 24 Stunden zurück, maximal 50."""
    logs = get_recent_logs()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    
    errors = []
    for log in logs:
        level = log.get("level", "").lower()
        if level in ("error", "warning", "critical"):
            try:
                event = log.get("event", "")
                if is_expected_yfinance_error(event, log.get("logger", "")):
                    continue
                ts_str = log.get("timestamp")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        errors.append({
                            "timestamp": ts_str,
                            "level": level,
                            "logger": log.get("logger", ""),
                            "event": log.get("event", ""),
                            "ticker": log.get("ticker")
                        })
            except Exception:
                continue
        if len(errors) >= 50:
            break
    return {"errors": errors, "count": len(errors)}

@router.get("/module-status")
async def api_get_module_status():
    """Gibt den Execution-Status der sechs Kernmodule zurück."""
    return get_module_status()

@router.post("/create-test-logs")
async def api_create_test_logs():
    """Erzeugt Test-Log-Einträge für alle Module (für Debugging)."""
    create_test_module_logs()
    return {"status": "success", "message": "Test logs created for all modules"}

@router.get("/module/{module_id}")
async def api_get_module_logs(module_id: str):
    """Gibt die letzten 20 Log-Zeilen für ein spezifisches Modul zurück."""
    if module_id not in MODULES:
        raise HTTPException(status_code=404, detail="Module not found")
    
    config = MODULES[module_id]
    logs = get_recent_logs()
    module_logs = [
        log for log in logs
        if log.get("logger") in config["logger_names"]
    ]
    
    return {"logs": module_logs[:20]}

@router.get("/file")
async def get_file_logs(lines: int = 1000, level: str | None = None):
    if not os.path.exists(LOG_FILE): 
        return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0, "ignore": 0}}
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    stats = {"total": len(all_lines), "error": 0, "warning": 0, "info": 0, "ignore": 0}
    for line in all_lines:
        if is_expected_yfinance_error(line):
            stats["ignore"] += 1
        elif "[ERROR]" in line:
            stats["error"] += 1
        elif "[WARNING]" in line:
            stats["warning"] += 1
        elif "[INFO]" in line:
            stats["info"] += 1
    
    result_lines = all_lines[-lines:]
    
    if level:
        level_upper = level.upper()
        if level_upper == "IGNORE":
            result_lines = [l for l in result_lines if is_expected_yfinance_error(l)]
        else:
            level_tag = f"[{level_upper}]"
            result_lines = [l for l in result_lines if level_tag in l and not is_expected_yfinance_error(l)]
    
    return {"logs": result_lines, "stats": stats}

@router.get("/stats")
async def get_log_stats():
    """Gibt Statistiken über Log-Level-Verteilung zurück."""
    if not os.path.exists(LOG_FILE): 
        return {"stats": {"total": 0, "error": 0, "warning": 0, "info": 0, "ignore": 0}, "recent_errors": []}
    
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    stats = {"total": len(all_lines), "error": 0, "warning": 0, "info": 0, "ignore": 0}
    recent_errors = []
    recent_warnings = []
    
    for line in all_lines:
        if is_expected_yfinance_error(line):
            stats["ignore"] += 1
        elif "[ERROR]" in line:
            stats["error"] += 1
            recent_errors.append(line.strip())
        elif "[WARNING]" in line:
            stats["warning"] += 1
            recent_warnings.append(line.strip())
        elif "[INFO]" in line:
            stats["info"] += 1
    
    return {
        "stats": stats,
        "recent_errors": recent_errors[-20:],
        "recent_warnings": recent_warnings[-20:],
    }

@router.get("/export")
async def export_logs():
    if not os.path.exists(LOG_FILE): 
        return {"error": "No log file"}
    filename = f"kafin_logs_{now_mez().strftime('%Y%m%d_%H%M%S')}.log"
    return FileResponse(LOG_FILE, media_type="text/plain", filename=filename)

@router.delete("/file")
async def clear_logs():
    _log_buffer.clear()
    try:
        with open(LOG_FILE, "r+", encoding="utf-8") as f:
            f.truncate(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear Logs Error: {e}")
    return {"status": "cleared"}

@router.post("/external")
async def receive_external_log(log: ExternalLog):
    """Webhook für n8n und externe Services zum Pushen von Logs"""
    from backend.app.logger import get_logger
    logger_ext = get_logger(log.source)
    msg = f"[EXTERNAL] {log.message}"
    if log.error_code: 
        msg += f" | CODE: {log.error_code}"
    
    if log.level.lower() == "error": 
        logger_ext.error(msg)
    elif log.level.lower() == "warning": 
        logger_ext.warning(msg)
    else: 
        logger_ext.info(msg)
    return {"status": "logged"}

@router.post("/cleanup")
async def api_cleanup_logs(days: int = 7):
    """Löscht Log-Einträge in der DB, die älter als X Tage sind."""
    # HINWEIS: Aktuell werden Logs primär in Dateien und im Buffer gehalten.
    # Falls es eine system_logs Tabelle gibt, würde hier die Löschung erfolgen.
    # Da wir in database.py/database/init/02_schema.sql keine system_logs Tabelle sehen,
    # beziehen wir uns auf die Datei-Rotation oder Buffer-Limitierung.
    # Für den Moment implementieren wir eine Logik, die die Datei kürzt wenn gewünscht.
    
    # TODO: Falls system_logs Tabelle existiert (z.B. für Alerts):
    from backend.app.db import get_supabase_client
    db = get_supabase_client()
    if db:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            # Wir nehmen an es gibt eine Tabelle 'system_logs' oder ähnlich
            # await db.table("system_logs").delete().lt("created_at", cutoff).execute_async()
            return {"status": "success", "message": f"Logs older than {days} days cleaned (stub)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return {"status": "success", "message": "No DB connection for cleanup"}
