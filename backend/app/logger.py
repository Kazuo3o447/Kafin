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
from typing import List, Dict, Any
from collections import deque
import json
from datetime import datetime

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
    # Stdlib-Root-Logger auf INFO setzen
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
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

