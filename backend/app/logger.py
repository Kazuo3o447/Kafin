"""
logger — Zentraler Logger der Anwendung

Input:  Log-Messages und Level
Output: Standardausgabe (Stdout) mit Formatierung
Deps:   logging
Config: environment (aus config)
API:    Keine
"""
import logging
import sys
from backend.app.config import settings

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Verhindere doppelte Handler
    if not logger.handlers:
        level = logging.DEBUG if settings.environment == "dev" else logging.INFO
        logger.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Beispiel-Initialisierung
logger = get_logger(__name__)
