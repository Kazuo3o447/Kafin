"""
PostgreSQL Drop-in Adapter für Supabase-Client-API.

Implementiert dieselbe Query-Builder-Syntax:
  db.table("x").select("*").eq("col", val).execute()
  db.table("x").insert({...}).execute()
  db.table("x").update({...}).eq("col", val).execute()
  db.table("x").upsert({...}, on_conflict="col").execute()
  db.table("x").delete().eq("col", val).execute()

Gibt ExecuteResult(data=[...]) zurück — kompatibel
mit Supabase-Response (result.data).
"""
import asyncio
import asyncpg
import json
from typing import Any, Optional
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Connection Pool (lazy init)
_pool: Optional[asyncpg.Pool] = None
_pool_lock: Optional[asyncio.Lock] = None


def _row_to_dict(row: asyncpg.Record) -> dict:
    """Konvertiert asyncpg Record zu dict,
    UUID → str, datetime → isoformat."""
    import uuid
    from datetime import datetime, date
    result = {}
    for k, v in dict(row).items():
        if isinstance(v, uuid.UUID):
            result[k] = str(v)
        elif isinstance(v, (datetime, date)):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def get_pool() -> asyncpg.Pool:
    global _pool
    global _pool_lock
    if _pool is not None:
        return _pool

    if _pool_lock is None:
        _pool_lock = asyncio.Lock()

    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30,
                init=_init_connection,
            )
    return _pool


async def close_pool() -> None:
    """Schließt den globalen Connection Pool beim Shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _init_connection(conn: asyncpg.Connection):
    """Konfiguriert jede neue Connection."""
    # JSON-Codec für JSONB
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )

    # pgvector-Codec, falls verfügbar
    try:
        from pgvector.asyncpg import register_vector

        await register_vector(conn)
    except Exception as e:
        logger.debug(f"pgvector Codec nicht registriert: {e}")


class ExecuteResult:
    """Kompatibel mit Supabase ExecuteResult."""
    def __init__(self, data: list):
        self.data = data


class QueryBuilder:
    """
    Baut SQL-Queries aus dem Supabase-artigen API.
    Alle Methoden geben self zurück (chaining).
    execute() ist nur Legacy-Fallback.
    In Async-Kontexten execute_async() verwenden.
    """

    def __init__(self, table: str):
        self._table   = table
        self._op      = None          # select/insert/update/upsert/delete
        self._columns = "*"
        self._data    = None          # dict für insert/update/upsert
        self._filters: list[tuple] = []
        self._order_col   = None
        self._order_desc  = False
        self._limit_val   = None
        self._on_conflict = None

    # ── Query-Typ ──────────────────────────────────
    def select(self, columns: str = "*") -> "QueryBuilder":
        self._op      = "select"
        self._columns = columns
        return self

    def insert(self, data: dict | list) -> "QueryBuilder":
        self._op   = "insert"
        self._data = data
        return self

    def update(self, data: dict) -> "QueryBuilder":
        self._op   = "update"
        self._data = data
        return self

    def upsert(
        self,
        data: dict | list,
        on_conflict: str = "id",
    ) -> "QueryBuilder":
        self._op          = "upsert"
        self._data        = data
        self._on_conflict = on_conflict
        return self

    def delete(self) -> "QueryBuilder":
        self._op = "delete"
        return self

    # ── Filter ────────────────────────────────────
    def eq(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("eq", col, val))
        return self

    def neq(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("neq", col, val))
        return self

    def gte(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("lte", col, val))
        return self

    def gt(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("gt", col, val))
        return self

    def lt(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("lt", col, val))
        return self

    def ilike(self, col: str, pattern: str) -> "QueryBuilder":
        self._filters.append(("ilike", col, pattern))
        return self

    def in_(self, col: str, values: list) -> "QueryBuilder":
        self._filters.append(("in", col, values))
        return self

    def is_(self, col: str, val: Any) -> "QueryBuilder":
        self._filters.append(("is", col, val))
        return self

    # ── Modifikatoren ─────────────────────────────
    def order(
        self,
        col: str,
        desc: bool = False,
    ) -> "QueryBuilder":
        self._order_col  = col
        self._order_desc = desc
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit_val = n
        return self

    # ── SQL-Generierung ───────────────────────────
    def _build_where(
        self, params: list, offset: int = 1
    ) -> str:
        """Gibt WHERE-Klausel + befüllte params zurück."""
        clauses = []
        for f in self._filters:
            op, col, val = f
            p_idx = len(params) + offset
            if op == "eq":
                clauses.append(f'"{col}" = ${p_idx}')
                params.append(val)
            elif op == "neq":
                clauses.append(f'"{col}" != ${p_idx}')
                params.append(val)
            elif op == "gte":
                clauses.append(f'"{col}" >= ${p_idx}')
                params.append(val)
            elif op == "lte":
                clauses.append(f'"{col}" <= ${p_idx}')
                params.append(val)
            elif op == "gt":
                clauses.append(f'"{col}" > ${p_idx}')
                params.append(val)
            elif op == "lt":
                clauses.append(f'"{col}" < ${p_idx}')
                params.append(val)
            elif op == "ilike":
                clauses.append(
                    f'"{col}" ILIKE ${p_idx}'
                )
                params.append(val)
            elif op == "in":
                clauses.append(
                    f'"{col}" = ANY(${p_idx})'
                )
                params.append(val)
            elif op == "is":
                if val is None:
                    clauses.append(f'"{col}" IS NULL')
                else:
                    clauses.append(
                        f'"{col}" IS NOT NULL'
                    )
        return (
            "WHERE " + " AND ".join(clauses)
            if clauses else ""
        )

    def _build_order_limit(self) -> str:
        parts = []
        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            parts.append(
                f'ORDER BY "{self._order_col}" {direction}'
            )
        if self._limit_val is not None:
            parts.append(f"LIMIT {self._limit_val}")
        return " ".join(parts)

    async def _execute_async(self) -> ExecuteResult:
        pool = await get_pool()
        async with pool.acquire() as conn:
            try:
                if self._op == "select":
                    return await self._select(conn)
                elif self._op == "insert":
                    return await self._insert(conn)
                elif self._op == "update":
                    return await self._update(conn)
                elif self._op == "upsert":
                    return await self._upsert(conn)
                elif self._op == "delete":
                    return await self._delete(conn)
                else:
                    return ExecuteResult([])
            except Exception as e:
                logger.error(
                    f"DB Error [{self._op}] "
                    f"{self._table}: {e}"
                )
                return ExecuteResult([])

    async def _select(
        self, conn: asyncpg.Connection
    ) -> ExecuteResult:
        params: list = []
        where = self._build_where(params)
        order_limit = self._build_order_limit()
        # Spalten-Parsing (komma-getrennt oder *)
        cols = (
            "*" if self._columns.strip() == "*"
            else ", ".join(
                f'"{c.strip()}"'
                for c in self._columns.split(",")
            )
        )
        sql = (
            f'SELECT {cols} FROM "{self._table}" '
            f'{where} {order_limit}'
        )
        rows = await conn.fetch(sql, *params)
        return ExecuteResult([_row_to_dict(r) for r in rows])

    async def _insert(
        self, conn: asyncpg.Connection
    ) -> ExecuteResult:
        records = (
            self._data
            if isinstance(self._data, list)
            else [self._data]
        )
        results = []
        for rec in records:
            cols = list(rec.keys())
            col_sql = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(cols))
            )
            vals = [
                json.dumps(v)
                if isinstance(v, (dict, list)) else v
                for v in rec.values()
            ]
            sql = (
                f'INSERT INTO "{self._table}" '
                f'({col_sql}) VALUES ({placeholders}) '
                f'RETURNING *'
            )
            row = await conn.fetchrow(sql, *vals)
            if row:
                results.append(_row_to_dict(row))
        return ExecuteResult(results)

    async def _update(
        self, conn: asyncpg.Connection
    ) -> ExecuteResult:
        params: list = []
        set_parts = []
        for col, val in (self._data or {}).items():
            idx = len(params) + 1
            set_parts.append(f'"{col}" = ${idx}')
            params.append(
                json.dumps(val)
                if isinstance(val, (dict, list)) else val
            )
        if not set_parts:
            return ExecuteResult([])
        set_sql = ", ".join(set_parts)
        where   = self._build_where(params)
        sql = (
            f'UPDATE "{self._table}" SET {set_sql} '
            f'{where} RETURNING *'
        )
        rows = await conn.fetch(sql, *params)
        return ExecuteResult([_row_to_dict(r) for r in rows])

    async def _upsert(
        self, conn: asyncpg.Connection
    ) -> ExecuteResult:
        records = (
            self._data
            if isinstance(self._data, list)
            else [self._data]
        )
        results = []
        conflict_cols = (
            self._on_conflict.split(",")
            if self._on_conflict else ["id"]
        )
        conflict_sql = ", ".join(
            f'"{c.strip()}"' for c in conflict_cols
        )
        for rec in records:
            cols = list(rec.keys())
            col_sql = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(
                f"${i+1}" for i in range(len(cols))
            )
            vals = [
                json.dumps(v)
                if isinstance(v, (dict, list)) else v
                for v in rec.values()
            ]
            update_parts = ", ".join(
                f'"{c}" = EXCLUDED."{c}"'
                for c in cols
                if c not in conflict_cols
            )
            sql = (
                f'INSERT INTO "{self._table}" '
                f'({col_sql}) VALUES ({placeholders}) '
                f'ON CONFLICT ({conflict_sql}) '
                f'DO UPDATE SET {update_parts} '
                f'RETURNING *'
            )
            row = await conn.fetchrow(sql, *vals)
            if row:
                results.append(_row_to_dict(row))
        return ExecuteResult(results)

    async def _delete(
        self, conn: asyncpg.Connection
    ) -> ExecuteResult:
        params: list = []
        where = self._build_where(params)
        if not where:
            # Sicherheit: kein DELETE ohne WHERE
            logger.warning(
                f"DELETE ohne WHERE auf {self._table}"
                " — abgebrochen"
            )
            return ExecuteResult([])
        sql = (
            f'DELETE FROM "{self._table}" '
            f'{where} RETURNING *'
        )
        rows = await conn.fetch(sql, *params)
        return ExecuteResult([_row_to_dict(r) for r in rows])

    def execute(self) -> ExecuteResult:
        """
        Legacy-Sync-Wrapper für bestehenden Code.

        In Sync-Kontexten wird die Query direkt via asyncio.run() ausgeführt.
        Falls bereits ein Event-Loop läuft, wird die Query in einem separaten
        Thread mit eigenem Event-Loop ausgeführt, um Deadlocks zu vermeiden.
        """
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(self._execute_async())

            import threading

            result: dict[str, Any] = {}
            error: dict[str, BaseException] = {}

            def _runner() -> None:
                try:
                    result["value"] = asyncio.run(self._execute_async())
                except BaseException as exc:  # pragma: no cover - defensive
                    error["exc"] = exc

            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            thread.join(timeout=30)

            if thread.is_alive():
                raise TimeoutError(
                    f"execute() Timeout für {self._table}"
                )
            if error:
                raise error["exc"]
            return result.get("value", ExecuteResult([]))
        except Exception as e:
            logger.error(f"execute() Fehler: {e}")
            return ExecuteResult([])

    async def execute_async(self) -> ExecuteResult:
        """
        Native async Version von execute().
        In FastAPI-Routes immer bevorzugen.
        """
        return await self._execute_async()


class DatabaseClient:
    """Drop-in Ersatz für Supabase Client."""

    def table(self, table_name: str) -> QueryBuilder:
        return QueryBuilder(table_name)
    
    async def execute(self, query: str, *args):
        """Führt eine rohe SQL-Query aus (für init_db.py)."""
        pool = await _get_pool()
        async with pool.acquire() as conn:
            if args:
                return await conn.execute(query, *args)
            else:
                return await conn.execute(query)


# Singleton
_db_client: Optional[DatabaseClient] = None


def get_db_client() -> DatabaseClient:
    """Gibt den PostgreSQL-Client zurück."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client


# Kompatibilitäts-Alias
def get_supabase_client() -> DatabaseClient:
    """
    Drop-in Ersatz für alten get_supabase_client().
    Alle 177 Aufrufe im Code bleiben unverändert.
    """
    return get_db_client()
