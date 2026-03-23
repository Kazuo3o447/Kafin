"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin, routers
Config: app_name, environment
"""
import asyncio
import os
from contextlib import asynccontextmanager
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
from backend.app.routers.journal import router as journal_router

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    # ── STARTUP ─────────────────────────
    try:
        from backend.app.database import get_pool
        await get_pool()
        logger.info(
            "PostgreSQL Connection Pool initialisiert"
        )
    except Exception as e:
        logger.error(f"PostgreSQL Fehler: {e}")

    logger.info(
        f"{settings.app_name} [{settings.environment}]"
    )
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus AKTIV")

    await ensure_watchlist_populated()
    await ensure_daily_snapshots_table()
    log_schema_extension_sql()

    # Automatische Migrations ausführen
    try:
        from backend.app.database import get_pool
        pool = await get_pool()
        await _run_pending_migrations(pool)
    except Exception as e:
        logger.warning(f"Migrations Fehler: {e}")

    # Cache-Warmup (non-blocking)
    async def _warm():
        try:
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
            logger.info("Cache-Warmup abgeschlossen")
        except Exception as e:
            logger.warning(f"Warmup Fehler: {e}")

    asyncio.create_task(_warm())

    # Embedding-Warmup (non-blocking)
    async def _warm_embeddings():
        try:
            from backend.app.embeddings import embed_text
            await embed_text("Kafin startup test")
            logger.info("Embedding-Modell bereit")
        except Exception as e:
            logger.warning(f"Embedding nicht geladen: {e}")

    asyncio.create_task(_warm_embeddings())

    # Periodischer Usage-Flush (alle 5min)
    async def _periodic_flush():
        while True:
            await asyncio.sleep(300)
            try:
                from backend.app.analysis.usage_tracker\
                    import flush_to_db
                await flush_to_db()
            except Exception:
                pass

    asyncio.create_task(_periodic_flush())

    # Watchlist Warm-Start
    async def _warm_watchlist():
        try:
            from backend.app.memory.watchlist import (
                get_watchlist
            )
            from backend.app.cache import cache_get
            wl = await get_watchlist()
            if not wl:
                return
            cache_key = "watchlist:enriched:v2"
            if not await cache_get(cache_key):
                from backend.app.routers.watchlist import (
                    api_watchlist_enriched
                )
                await api_watchlist_enriched()
                logger.info(
                    "Watchlist Enriched Cache vorgewärmt."
                )
        except Exception as e:
            logger.debug(f"Watchlist warm Fehler: {e}")

    asyncio.create_task(_warm_watchlist())

    yield  # Server läuft

    # ── SHUTDOWN ────────────────────────
    try:
        from backend.app.database import close_pool
        await close_pool()
        logger.info("PostgreSQL Pool geschlossen")
    except Exception as e:
        logger.warning(f"Pool-Close Fehler: {e}")

    try:
        from backend.app.analysis.usage_tracker\
            import flush_to_db
        await flush_to_db()
        logger.info("Letzter Usage-Flush OK")
    except Exception:
        pass

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API für die Kafin Earnings-Trading-Plattform",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(journal_router)


async def _run_pending_migrations(pool) -> None:
    """Wendet alle noch nicht angewendeten SQL-Migrations an."""
    migrations_dir = os.path.join(os.getcwd(), "database", "migrations")
    if not os.path.isdir(migrations_dir):
        return

    sql_files = sorted(
        f for f in os.listdir(migrations_dir) if f.endswith(".sql")
    )

    async with pool.acquire() as conn:
        # Versionstabelle sicherstellen
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT NOW()
            )
        """)

        already_applied = {
            row["filename"]
            for row in await conn.fetch(
                "SELECT filename FROM schema_migrations"
            )
        }

        for filename in sql_files:
            if filename in already_applied:
                logger.debug(f"Migration bereits angewendet: {filename}")
                continue

            filepath = os.path.join(migrations_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()

            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)",
                    filename,
                )
                logger.info(f"Migration angewendet: {filename}")
            except Exception as e:
                logger.error(f"Migration fehlgeschlagen [{filename}]: {e}")
                # Nicht abbrechen — nächste Migration versuchen


@app.on_event("startup")
async def _run_migrations():
    from backend.app.database import get_pool
    pool = await get_pool()
    await _run_pending_migrations(pool)


@app.post("/api/admin/backup-database")
async def api_backup_database():
    """
    Löst einen PostgreSQL Backup aus.
    Speichert in /app/backups/ (Volume gemountet).
    Nur aus dem internen Netz aufrufbar.
    """
    import subprocess
    import os
    from datetime import datetime

    backup_dir = "/app/backups"
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/kafin_{ts}.sql.gz"

    pg_host = "postgres"
    pg_user = "kafin"
    pg_db   = "kafin"
    pg_pass = os.getenv(
        "POSTGRES_PASSWORD", "kafin_local_dev"
    )

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = pg_pass

        # pg_dump → gzip
        dump = subprocess.Popen(
            [
                "pg_dump",
                "-h", pg_host,
                "-U", pg_user,
                "-d", pg_db,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        gzip_proc = subprocess.Popen(
            ["gzip"],
            stdin=dump.stdout,
            stdout=open(backup_file, "wb"),
            stderr=subprocess.PIPE,
        )
        dump.stdout.close()
        gzip_proc.wait()
        dump.wait()

        size_mb = os.path.getsize(backup_file) / 1024 / 1024

        # Alte Backups (>7 Tage) löschen
        import glob, time
        cutoff = time.time() - 7 * 86400
        removed = []
        for f in glob.glob(f"{backup_dir}/*.sql.gz"):
            if os.path.getmtime(f) < cutoff and f != backup_file:
                os.remove(f)
                removed.append(os.path.basename(f))

        logger.info(
            f"Backup erstellt: {backup_file} "
            f"({size_mb:.1f}MB)"
        )
        return {
            "success":     True,
            "file":        backup_file,
            "size_mb":     round(size_mb, 2),
            "removed_old": removed,
            "timestamp":   ts,
        }

    except FileNotFoundError:
        # pg_dump nicht im Backend-Container
        # → Verweis auf docker-compose run
        return {
            "success": False,
            "error":   "pg_dump nicht verfügbar. "
                       "Nutze: docker-compose run "
                       "kafin-backup",
        }
    except Exception as e:
        logger.error(f"Backup Fehler: {e}")
        return {"success": False, "error": str(e)}
