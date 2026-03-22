from fastapi import APIRouter, HTTPException, Query
from backend.app.logger import get_logger, log_custom_search_terms_sql, get_schema_extension_sql
from backend.app.database import get_pool
from backend.app.embeddings import save_embedding

logger = get_logger(__name__)

router = APIRouter(tags=["admin-ops"])

@router.post("/init-tables")
async def api_admin_init_tables():
    """Gibt das SQL für Phase-4A Tabellen zurück."""
    sql = get_schema_extension_sql()
    logger.info("Phase-4A Tabellen SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_schema_extension_sql())
    log_custom_search_terms_sql()
    logger.info("API Call: admin init tables SQL ausgegeben")
    return {"status": "success", "sql": sql}

@router.post("/embeddings/backfill")
async def api_embeddings_backfill(
    table: str = Query(
        "short_term_memory",
        description="Tabelle: short_term_memory | audit_reports"
    ),
    limit: int = Query(100),
):
    """
    Generiert Embeddings für Einträge ohne Embedding.
    Für Initial-Befüllung nach Migration.
    """
    if table not in (
        "short_term_memory", "audit_reports",
        "long_term_memory"
    ):
        raise HTTPException(400, "Ungültige Tabelle")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT id, ticker, bullet_points, '
            f'report_text FROM "{table}" '
            f'WHERE embedding IS NULL '
            f'LIMIT $1',
            limit,
        )

    processed = 0
    for row in rows:
        # Text für Embedding zusammenbauen
        if table == "short_term_memory":
            bps = row.get("bullet_points") or []
            text = (
                f"{row['ticker']}: "
                + " | ".join(
                    str(b) for b in
                    (bps if isinstance(bps, list)
                     else [bps])[:3]
                )
            )
        elif table == "audit_reports":
            text = (
                f"{row.get('ticker', '')}: "
                + str(row.get("report_text", ""))[:500]
            )
        else:
            text = str(row.get("insight", ""))

        ok = await save_embedding(
            table, str(row["id"]), text
        )
        if ok:
            processed += 1

    return {
        "processed": processed,
        "total":     len(rows),
        "table":     table,
    }
