"""
logger — Zentraler Logger der Anwendung (mit structlog)

Input:  Log-Messages und Level
Output: Standardausgabe (Stdout) mit strukturierter Formatierung & In-Memory Logs Buffer
Deps:   structlog
Config: environment (aus config)
API:    Keine
"""
import structlog
import logging
import sys
from typing import List, Dict, Any
from collections import deque
import json
from datetime import datetime

# In-Memory Buffer for the Admin Panel
LOG_BUFFER_SIZE = 500
_log_buffer: deque = deque(maxlen=LOG_BUFFER_SIZE)

def get_recent_logs() -> List[Dict[str, Any]]:
    return list(_log_buffer)

def _memory_buffer_processor(logger, log_method, event_dict):
    """Fügt Log-Einträge in den globalen Buffer ein"""
    
    # We copy the dict to avoid subsequent processors mutating the stored version
    log_entry = dict(event_dict)
    
    if "timestamp" not in log_entry:
        log_entry["timestamp"] = datetime.utcnow().isoformat()
    
    _log_buffer.appendleft(log_entry)
    
    return event_dict

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            _memory_buffer_processor,
            structlog.dev.ConsoleRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

setup_logging()

def get_logger(name: str):
    return structlog.get_logger(name)

logger = get_logger(__name__)
