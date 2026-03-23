from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import time
from datetime import datetime, timedelta
import httpx

from backend.app.logger import get_logger
from backend.app.db import get_supabase_client
from backend.app.config import settings

logger = get_logger(__name__)

router = APIRouter(tags=["system"])

class HealthCheckResponse(BaseModel):
    status: str
    version: str

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Prüft, ob die API erreichbar ist."""
    return HealthCheckResponse(status="ok", version="1.0.0")

@router.post("/api/n8n/setup")
async def api_n8n_setup():
    """Erstellt die n8n-Workflows automatisch."""
    from backend.app.n8n_setup import setup_workflows
    await setup_workflows()
    return {"status": "success", "message": "n8n Workflows wurden erstellt"}

@router.post("/api/telegram/test")
async def api_telegram_test():
    """Sendet eine Test-Nachricht per Telegram."""
    from backend.app.alerts.telegram import send_telegram_alert
    await send_telegram_alert("🧪 Kafin Systemtest: Telegram-Verbindung OK.")
    return {"status": "success", "message": "Test-Nachricht gesendet"}

@router.get("/api/diagnostics/db")
async def api_diagnostics_db():
    """Prüft den Datenstand aller Supabase-Tabellen."""
    db = get_supabase_client()
    if db is None:
        return {"status": "error", "message": "Supabase nicht verbunden"}

    results = {}
    tables = ["watchlist", "short_term_memory", "daily_snapshots", "macro_snapshots", "audit_reports"]
    for table in tables:
        try:
            data = await db.table(table).select("*", count="exact").limit(0).execute_async()
            results[table] = {"count": data.count if hasattr(data, "count") else "unknown", "status": "ok"}
        except Exception as e:
            results[table] = {"count": 0, "status": f"error: {str(e)[:100]}"}

    return {"status": "success", "tables": results}

@router.get("/api/diagnostics/full")
async def full_system_diagnostics():
    from backend.app.data.finnhub import get_company_news
    from backend.app.data.fmp import get_company_profile as fmp_profile
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.analysis.deepseek import call_deepseek
    from backend.app.analysis.finbert import analyze_sentiment
    
    logger.info("=== Starting Full System Diagnostics ===")
    
    results = {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "services": {}}
    
    async def measure(func, *args):
        t0 = time.time()
        try:
            res = await func(*args) if args else await func()
            return res, round((time.time() - t0) * 1000)
        except Exception as e:
            logger.error(f"Error measuring {func.__name__}: {e}")
            raise

    # 1. Supabase
    logger.info("🔍 Testing Supabase connection...")
    try:
        t0 = time.time()
        db = get_supabase_client()
        wl = await db.table("watchlist").select("ticker").limit(1).execute_async() if db else None
        ms = round((time.time() - t0) * 1000)
        results["services"]["supabase"] = {"status": "ok" if wl else "error", "latency_ms": ms, "details": "DB connected"}
        logger.info(f"✅ Supabase: OK ({ms}ms)")
    except Exception as e:
        results["services"]["supabase"] = {"status": "error", "error_code": "DB_CONN_ERR", "details": str(e)}
        logger.error(f"❌ Supabase: ERROR - {e}")

    # 2. Finnhub API
    logger.info("🔍 Testing Finnhub API...")
    try:
        from backend.app.utils.timezone import now_mez
        now = now_mez()
        from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")
        res, ms = await measure(get_company_news, "AAPL", from_date, to_date)
        results["services"]["finnhub"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ Finnhub: OK ({ms}ms, {len(res) if res else 0} items)")
    except Exception as e:
        results["services"]["finnhub"] = {"status": "error", "error_code": "FINNHUB_API_ERR", "details": repr(e)}
        logger.error(f"❌ Finnhub: ERROR - {e}")

    # 3. FMP API
    logger.info("🔍 Testing FMP API...")
    try:
        res, ms = await measure(fmp_profile, "AAPL")
        results["services"]["fmp"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ FMP: OK ({ms}ms)")
    except Exception as e:
        results["services"]["fmp"] = {"status": "error", "error_code": "FMP_API_ERR", "details": repr(e)}
        logger.error(f"❌ FMP: ERROR - {e}")

    # 4. FRED API
    logger.info("🔍 Testing FRED API...")
    try:
        res, ms = await measure(get_macro_snapshot)
        results["services"]["fred"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ FRED: OK ({ms}ms)")
    except Exception as e:
        results["services"]["fred"] = {"status": "error", "error_code": "FRED_API_ERR", "details": repr(e)}
        logger.error(f"❌ FRED: ERROR - {e}")

    # 5. AI Services
    logger.info("🔍 Testing DeepSeek API...")
    try:
        res, ms = await measure(call_deepseek, "Reply OK", "Test")
        results["services"]["deepseek"] = {"status": "ok", "latency_ms": ms, "details": "LLM responsive"}
        logger.info(f"✅ DeepSeek: OK ({ms}ms)")
    except Exception as e:
        results["services"]["deepseek"] = {"status": "error", "error_code": "DEEPSEEK_ERR", "details": repr(e)}
        logger.error(f"❌ DeepSeek: ERROR - {e}")
        
    logger.info("🔍 Testing FinBERT model...")
    try:
        t0 = time.time()
        await asyncio.to_thread(analyze_sentiment, "Test sentence.")
        ms = round((time.time() - t0) * 1000)
        results["services"]["finbert"] = {"status": "ok", "latency_ms": ms, "details": "Model loaded"}
        logger.info(f"✅ FinBERT: OK ({ms}ms)")
    except Exception as e:
        results["services"]["finbert"] = {"status": "error", "error_code": "FINBERT_ERR", "details": repr(e)}
        logger.error(f"❌ FinBERT: ERROR - {e}")

    # 6. Telegram
    logger.info("🔍 Testing Telegram connection...")
    try:
        from backend.app.alerts.telegram import send_telegram_alert
        await send_telegram_alert("🧪 Systemcheck: Alle APIs getestet.")
        results["services"]["telegram"] = {"status": "ok", "details": "Notification sent"}
        logger.info("✅ Telegram: OK")
    except Exception as e:
        results["services"]["telegram"] = {"status": "error", "error_code": "TELEGRAM_ERR", "details": repr(e)}
        logger.error(f"❌ Telegram: ERROR - {e}")

    # 7. n8n
    logger.info("🔍 Testing n8n connection...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://kafin-n8n:5678/healthz", timeout=5.0)
            results["services"]["n8n"] = {"status": "ok" if response.status_code == 200 else "warning", "details": f"Status {response.status_code}"}
            logger.info(f"✅ n8n: OK (status {response.status_code})")
    except Exception as e:
        results["services"]["n8n"] = {"status": "error", "error_code": "N8N_ERR", "details": repr(e)}
        logger.error(f"❌ n8n: ERROR - {e}")

    # 8. Alpaca Paper Trading
    logger.info("🔍 Testing Alpaca Paper Trading...")
    try:
        from backend.app.data.alpaca import get_alpaca_account, _configured
        if not _configured():
            results["services"]["alpaca"] = {
                "status":  "warning",
                "details": "ALPACA_API_KEY nicht gesetzt — Paper Trading deaktiviert",
            }
            logger.warning("⚠️ Alpaca: nicht konfiguriert")
        else:
            t0 = time.time()
            account = await get_alpaca_account()
            ms = round((time.time() - t0) * 1000)
            if account:
                equity = account.get("equity", 0)
                results["services"]["alpaca"] = {
                    "status":     "ok",
                    "latency_ms": ms,
                    "details":    f"Paper Trading aktiv · Equity ${equity:,.0f}",
                }
                logger.info(f"✅ Alpaca: OK ({ms}ms, equity ${equity:,.0f})")
            else:
                results["services"]["alpaca"] = {
                    "status":     "error",
                    "error_code": "ALPACA_AUTH_ERR",
                    "details":    "Account-Abfrage fehlgeschlagen — Keys prüfen",
                }
                logger.error("❌ Alpaca: Auth-Fehler")
    except Exception as e:
        results["services"]["alpaca"] = {
            "status":     "error",
            "error_code": "ALPACA_ERR",
            "details":    repr(e),
        }
        logger.error(f"❌ Alpaca: ERROR - {e}")

    # 9. CoinGlass
    logger.info("🔍 Testing CoinGlass API...")
    try:
        from backend.app.data.coinglass import get_btc_price_and_trend
        from backend.app.config import settings as _settings
        if not _settings.coinglass_api_key:
            results["services"]["coinglass"] = {
                "status":  "warning",
                "details": "COINGLASS_API_KEY nicht gesetzt — BTC-Derivate-Daten deaktiviert",
            }
            logger.warning("⚠️ CoinGlass: nicht konfiguriert")
        else:
            t0 = time.time()
            btc = await get_btc_price_and_trend()
            ms = round((time.time() - t0) * 1000)
            if btc and btc.get("price"):
                results["services"]["coinglass"] = {
                    "status":     "ok",
                    "latency_ms": ms,
                    "details":    f"BTC ${btc['price']:,.0f} · 7T {btc.get('change_7d_pct',0):+.1f}%",
                }
                logger.info(f"✅ CoinGlass: OK ({ms}ms)")
            else:
                results["services"]["coinglass"] = {
                    "status":  "warning",
                    "details": "Keine BTC-Daten erhalten — Free-Tier-Limit möglich",
                }
                logger.warning("⚠️ CoinGlass: keine Daten")
    except Exception as e:
        results["services"]["coinglass"] = {
            "status":     "error",
            "error_code": "COINGLASS_ERR",
            "details":    repr(e),
        }
        logger.error(f"❌ CoinGlass: ERROR - {e}")

    if any(s.get("status") == "error" for s in results["services"].values()):
        results["status"] = "degraded"
        logger.warning("⚠️ System status: DEGRADED")
    else:
        logger.info("✅ System status: OK")
    
    logger.info("=== Full System Diagnostics Complete ===")
    return results
