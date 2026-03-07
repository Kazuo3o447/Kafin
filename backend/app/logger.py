"""
logger — Zentraler Logger der Anwendung (mit structlog)

Input:  Log-Messages und Level
Output: Standardausgabe (Stdout) mit strukturierter Formatierung
Deps:   structlog
Config: environment (aus config)
API:    Keine
"""
import structlog
import logging
import sys

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
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
