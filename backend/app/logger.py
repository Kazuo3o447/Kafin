"""
logger — Zentraler Logger der Anwendung (structlog + stdlib)

Input:  Log-Messages und Level aus dem gesamten Backend
Output: Standardausgabe (Stdout) + In-Memory Buffer für Admin Panel
Deps:   structlog, logging (stdlib)
Config: Keine externe Konfiguration nötig.

WICHTIG: setup_logging() MUSS aufgerufen werden, bevor der erste Logger erzeugt wird.
Der In-Memory Buffer (_log_buffer) speichert die letzten LOG_BUFFER_SIZE Einträge
und wird über /api/logs vom Admin Panel abgerufen.
"""
import structlog
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import List, Dict, Any
from collections import deque
import json
import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# File Logging Configuration
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "kafin.log")

# ---------------------------------------------------------------------------
# Buffer: In-Memory Log-Speicher für Admin Panel
# ---------------------------------------------------------------------------
LOG_BUFFER_SIZE = 500
_log_buffer: deque = deque(maxlen=LOG_BUFFER_SIZE)

def get_recent_logs() -> List[Dict[str, Any]]:
    """Gibt die letzten LOG_BUFFER_SIZE Einträge zurück, neueste zuerst."""
    return list(_log_buffer)

def _memory_buffer_processor(logger, log_method, event_dict):
    """
    Structlog-Prozessor: Kopiert jeden Log-Eintrag in den globalen Buffer.
    Muss VOR dem ConsoleRenderer in der Prozessor-Kette stehen.
    Wir verwenden eine Kopie, damit spätere Prozessoren unsere gespeicherte
    Version nicht mehr verändern können.
    """
    log_entry = dict(event_dict)
    
    # Sicherstellen, dass ein Timestamp vorhanden ist
    if "timestamp" not in log_entry:
        log_entry["timestamp"] = datetime.utcnow().isoformat()
    
    # Levelname aus dem Methoden-Namen ableiten, falls nicht gesetzt
    if "level" not in log_entry:
        log_entry["level"] = log_method
    
    _log_buffer.appendleft(log_entry)
    
    return event_dict

# ---------------------------------------------------------------------------
# Module Status Helper
# ---------------------------------------------------------------------------
MODULES = {
    "finbert_pipeline": {
        "label": "FinBERT Pipeline",
        "success_pattern": re.compile(r"FinBERT", re.IGNORECASE),
        "logger_names": ["finbert", "news_processor"]
    },
    "sec_edgar": {
        "label": "SEC EDGAR Scanner",
        "success_pattern": re.compile(r"EDGAR", re.IGNORECASE),
        "logger_names": ["sec_edgar"]
    },
    "morning_briefing": {
        "label": "Morning Briefing",
        "success_pattern": re.compile(r"morning", re.IGNORECASE),
        "logger_names": ["report_generator"]
    },
    "sunday_report": {
        "label": "Sonntags-Report",
        "success_pattern": re.compile(r"sunday|sonntag|weekly", re.IGNORECASE),
        "logger_names": ["report_generator"]
    },
    "torpedo_monitor": {
        "label": "Torpedo Monitor",
        "success_pattern": re.compile(r"torpedo", re.IGNORECASE),
        "logger_names": ["torpedo_monitor"]
    },
    "n8n_scheduler": {
        "label": "n8n Scheduler",
        "success_pattern": re.compile(r"n8n", re.IGNORECASE),
        "logger_names": ["n8n"]
    }
}

def _relative_time(dt: datetime) -> str:
    """Gibt eine relative Zeit zurück wie 'vor 2 Stunden'."""
    now = datetime.utcnow()
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "gerade eben"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"vor {minutes} Minute{'n' if minutes != 1 else ''}"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"vor {hours} Stunde{'n' if hours != 1 else ''}"
    days = int(seconds // 86400)
    return f"vor {days} Tag{'en' if days != 1 else ''}"

def get_module_status() -> Dict[str, Any]:
    """Scans the last 500 log entries and extracts status per module."""
    status_result = {
        "modules": {},
        "generated_at": datetime.utcnow().isoformat()
    }
    
    logs = get_recent_logs()
    # Filter to last 500 (already limited by buffer)
    recent_logs = logs[:500]
    
    for module_id, config in MODULES.items():
        # Find logs for this module
        module_logs = [
            log for log in recent_logs
            if log.get("logger") in config["logger_names"]
        ]
        
        last_run = None
        last_error = None
        stats = ""
        status = "unknown"
        
        # Determine last run and last error
        for log in module_logs:
            ts_str = log.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                continue
            
            # Check for error or warning
            level = log.get("level", "").lower()
            if level in ("error", "warning", "critical"):
                if last_error is None or ts > datetime.fromisoformat(last_error.get("timestamp", "1970")):
                    last_error = {
                        "timestamp": ts_str,
                        "level": level,
                        "event": log.get("event", "")
                    }
            
            # Check for success pattern
            event = log.get("event", "")
            if config["success_pattern"].search(event):
                if last_run is None or ts > datetime.fromisoformat(last_run):
                    last_run = ts_str
        
        # Determine status
        if last_error:
            status = "error"
        elif last_run:
            # Check if last run is recent (within 24h)
            try:
                last_run_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                if datetime.utcnow() - last_run_dt < timedelta(hours=24):
                    status = "ok"
                else:
                    status = "warning"
            except Exception:
                status = "warning"
        else:
            status = "unknown"
        
        # Extract stats (simple heuristic: count of logs with success pattern)
        success_count = sum(1 for log in module_logs if config["success_pattern"].search(log.get("event", "")))
        if success_count > 0:
            stats = f"{success_count} Durchläufe heute"
        
        status_result["modules"][module_id] = {
            "label": config["label"],
            "status": status,
            "last_run": last_run,
            "last_run_relative": _relative_time(datetime.fromisoformat(last_run.replace("Z", "+00:00"))) if last_run else None,
            "last_error": last_error,
            "stats": stats,
            "recent_logs": []  # To be filled on-demand
        }
    
    return status_result

# ---------------------------------------------------------------------------
# Setup: Konfiguriert structlog und das stdlib-Logging-System
# ---------------------------------------------------------------------------
def setup_logging():
    """
    Verbindet structlog mit dem stdlib-Logging.
    So werden ALLE Log-Ausgaben — auch aus Bibliotheken wie httpx oder uvicorn —
    über die structlog-Pipeline geleitet und im Buffer gespeichert.
    
    Wichtig: cache_logger_on_first_use=False damit der Buffer-Prozessor
    bei JEDEM Log-Aufruf aktiv ausgeführt wird.
    """
    # File und Stream Handler
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[stream_handler, file_handler],
        level=logging.INFO
    )
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,          # Level-Filter (DEBUG entfernen wenn nicht nötig)
            structlog.processors.TimeStamper(fmt="iso"),# ISO-8601 Timestamp
            structlog.stdlib.add_log_level,             # Level-Feld hinzufügen
            structlog.stdlib.add_logger_name,           # Logger-Name hinzufügen
            _memory_buffer_processor,                   # <-- In-Memory Buffer füllen
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,  # Für stdlib-Bridge
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,                # KRITISCH: Nicht cachen → Buffer wird immer befüllt
    )

setup_logging()

def get_logger(name: str):
    """Erzeugt und gibt einen konfigurierten Logger zurück."""
    return structlog.get_logger(name)

logger = get_logger(__name__)

