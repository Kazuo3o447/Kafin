"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin, routers
Config: app_name, environment
"""
import asyncio
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.init_watchlist import ensure_watchlist_populated
from backend.app.init_db import (
    ensure_daily_snapshots_table,
    log_schema_extension_sql,
)

# Import modular routers
from backend.app.admin import router as admin_router
from backend.app.routers.data import router as data_router
from backend.app.routers.news import router as news_router
from backend.app.routers.reports import router as reports_router
from backend.app.routers.watchlist import router as watchlist_router
from backend.app.routers.web_intelligence import router as web_intel_router
from backend.app.routers.analysis import router as analysis_router
from backend.app.routers.shadow import router as shadow_router
from backend.app.routers.logs import router as logs_router
from backend.app.routers.system import router as system_router

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API für die Kafin Earnings-Trading-Plattform",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # PostgreSQL Connection Pool initialisieren
    try:
        from backend.app.database import get_pool
        await get_pool()
        logger.info("PostgreSQL Connection Pool initialisiert")
    except Exception as e:
        logger.error(f"PostgreSQL Connection Fehler: {e}")
    
    logger.info(f"Starter {settings.app_name} im [{settings.environment}] Modus.")
    logger.info("Admin Panel ist verfügbar bei /admin")
    
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus ist AKTIV. Es werden keine echten APIs aufgerufen.")
    
    await ensure_watchlist_populated()
    await ensure_daily_snapshots_table()
    log_schema_extension_sql()

    # API Usage Tabelle erstellen (einmalig)
    try:
        from backend.app.database import get_pool
        pool = await get_pool()
        migration = os.path.join(
            os.getcwd(), "database", "migrations", "04_api_usage.sql"
        )
        if os.path.exists(migration):
            with open(migration, "r") as f:
                sql = f.read()
            async with pool.acquire() as conn:
                await conn.execute(sql)
            logger.info("api_usage Tabelle bereit.")
    except Exception as e:
        logger.warning(f"api_usage Migration: {e}")

    # Periodischer Flush für API Usage alle 5 Minuten
    async def _periodic_flush():
        while True:
            await asyncio.sleep(300)
            try:
                from backend.app.analysis.usage_tracker import flush_to_db
                await flush_to_db()
            except Exception:
                pass

    asyncio.create_task(_periodic_flush())

    # Warm-Start für Market-Cache
    async def _warm():
        try:
            logger.info("Cache-Warm-Start...")
            from backend.app.data.market_overview import (
                get_market_overview,
                get_market_breadth,
                get_intermarket_signals,
            )
            await asyncio.gather(
                get_market_overview(),
                get_market_breadth(),
                get_intermarket_signals(),
                return_exceptions=True,
            )
            logger.info("Cache-Warm-Start abgeschlossen.")
        except Exception as e:
            logger.warning(f"Warm-Start Fehler: {e}")

    async def _warm_watchlist():
        """Watchlist Enriched im Hintergrund vorwärmen."""
        try:
            from backend.app.memory.watchlist import (
                get_watchlist
            )
            from backend.app.cache import cache_get
            wl = await get_watchlist()
            if not wl:
                return
            # Direkt die Cache-Funktion aufrufen
            # (triggert _fetch_ticker_data_sync für alle Ticker)
            cache_key = "watchlist:enriched:v2"
            if not cache_get(cache_key):
                # Nur wenn Cache kalt — ganzen Endpoint simulieren
                # Wir importieren den Router-Handler direkt
                from backend.app.routers.watchlist import (
                    api_watchlist_enriched
                )
                await api_watchlist_enriched()
                logger.info(
                    "Watchlist Enriched Cache vorgewärmt."
                )
        except Exception as e:
            logger.debug(f"Watchlist warm Fehler: {e}")

    # Watchlist separat — darf länger dauern
    asyncio.create_task(_warm_watchlist())
    asyncio.create_task(_warm())

    # Embedding-Modell vorwärmen
    async def _warm_embeddings():
        try:
            from backend.app.embeddings import embed_text
            await embed_text("Kafin startup test")
            logger.info("Embedding-Modell bereit.")
        except Exception as e:
            logger.warning(f"Embedding-Modell nicht geladen: {e}")

    asyncio.create_task(_warm_embeddings())


@app.on_event("shutdown")
async def shutdown_event():
    """Schließt externe Ressourcen sauber beim Server-Shutdown."""
    try:
        from backend.app.database import close_pool
        await close_pool()
        logger.info("PostgreSQL Connection Pool geschlossen")
    except Exception as e:
        logger.warning(f"Shutdown Pool Close Fehler: {e}")

# Register modular routers
app.include_router(admin_router)
app.include_router(data_router)
app.include_router(news_router)
app.include_router(reports_router)
app.include_router(watchlist_router)
app.include_router(web_intel_router)
app.include_router(analysis_router)
app.include_router(shadow_router)
app.include_router(logs_router)
app.include_router(system_router)
