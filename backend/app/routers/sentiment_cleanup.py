"""
Sentiment Cache Management Router
API-Endpunkte für Retention, Cleanup und Monitoring
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from backend.app.logger import get_logger
from backend.app.db import get_supabase_client

router = APIRouter()
logger = get_logger(__name__)


class CleanupRequest(BaseModel):
    days_to_keep: int = 30


@router.get("/api/sentiment/stats")
async def get_sentiment_stats():
    """
    Gibt aktuelle Speicherplatz-Statistiken für den Sentiment-Cache zurück.
    """
    try:
        db = get_supabase_client()
        if not db:
            raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
        
        # Monitoring-Funktion aufrufen
        result = await db.rpc("get_sentiment_storage_stats").execute_async()
        
        if result.data:
            stats = result.data[0]
            return {
                "status": "success",
                "stats": {
                    "total_records": stats.get("total_records", 0),
                    "table_size": stats.get("table_size", "0 kB"),
                    "avg_record_size_kb": stats.get("avg_record_size_kb", 0),
                    "oldest_record": stats.get("oldest_record"),
                    "newest_record": stats.get("newest_record"),
                    "material_events_count": stats.get("material_events_count", 0)
                }
            }
        else:
            return {"status": "success", "stats": {}}
            
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Sentiment-Stats: {e}")
        raise HTTPException(status_code=500, detail=f"Stats fehlgeschlagen: {e}")


@router.post("/api/sentiment/cleanup")
async def cleanup_sentiment_data(request: CleanupRequest):
    """
    Führt manuellen Cleanup durch mit konfigurierbarer Retention.
    
    Args:
        request: CleanupRequest mit days_to_keep (Standard: 30)
    """
    try:
        db = get_supabase_client()
        if not db:
            raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
        
        days_to_keep = max(1, min(365, request.days_to_keep))  # 1-365 Tage
        
        # Cleanup-Funktion aufrufen
        result = await db.rpc(
            "admin_cleanup_sentiment_data", 
            {"days_to_keep": days_to_keep}
        ).execute_async()
        
        deleted_count = 0
        if result.data:
            deleted_count = result.data[0].get("deleted_count", 0)
        
        # Speicheroptimierung nach Cleanup
        await db.rpc("optimize_sentiment_storage").execute_async()
        
        logger.info(f"Sentiment Cleanup: {deleted_count} Einträge gelöscht (Retention: {days_to_keep} Tage)")
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "retention_days": days_to_keep,
            "message": f"Cleanup abgeschlossen. {deleted_count} Einträge gelöscht."
        }
        
    except Exception as e:
        logger.error(f"Fehler beim Sentiment Cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup fehlgeschlagen: {e}")


@router.post("/api/sentiment/optimize")
async def optimize_sentiment_storage():
    """
    Optimiert den Speicherplatz durch VACUUM und Index-Neuaufbau.
    """
    try:
        db = get_supabase_client()
        if not db:
            raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
        
        await db.rpc("optimize_sentiment_storage").execute_async()
        
        logger.info("Sentiment Storage Optimization abgeschlossen")
        
        return {
            "status": "success",
            "message": "Speicheroptimierung abgeschlossen."
        }
        
    except Exception as e:
        logger.error(f"Fehler bei Speicheroptimierung: {e}")
        raise HTTPException(status_code=500, detail=f"Optimierung fehlgeschlagen: {e}")


@router.get("/api/sentiment/health")
async def sentiment_health_check():
    """
    Health-Check für Sentiment-Cache mit Empfehlungen.
    """
    try:
        db = get_supabase_client()
        if not db:
            raise HTTPException(status_code=500, detail="Datenbank nicht verfügbar")
        
        # Stats abrufen
        result = await db.rpc("get_sentiment_storage_stats").execute_async()
        
        if not result.data:
            return {"status": "warning", "message": "Keine Statistiken verfügbar"}
        
        stats = result.data[0]
        total_records = stats.get("total_records", 0)
        table_size = stats.get("table_size", "0 kB")
        
        # Health-Bewertung
        health_status = "healthy"
        recommendations = []
        
        # Größe bewerten
        if "MB" in table_size:
            size_mb = float(table_size.replace("MB", "").strip())
            if size_mb > 500:
                health_status = "critical"
                recommendations.append("Cache > 500MB - sofortiger Cleanup empfohlen")
            elif size_mb > 200:
                health_status = "warning"
                recommendations.append("Cache > 200MB - Cleanup empfohlen")
        
        # Anzahl Einträge bewerten
        if total_records > 100000:
            health_status = "critical"
            recommendations.append("Mehr als 100.000 Einträge - Retention reduzieren")
        elif total_records > 50000:
            health_status = "warning"
            recommendations.append("Mehr als 50.000 Einträge - überprüfen")
        
        # Alter der Daten
        oldest = stats.get("oldest_record")
        if oldest:
            from datetime import datetime, timezone
            try:
                oldest_date = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
                days_old = (datetime.now(timezone.utc) - oldest_date).days
                if days_old > 90:
                    recommendations.append(f"Daten älter als {days_old} Tage vorhanden")
            except:
                pass
        
        return {
            "status": health_status,
            "stats": {
                "total_records": total_records,
                "table_size": table_size,
                "oldest_record": oldest,
                "newest_record": stats.get("newest_record"),
                "material_events_count": stats.get("material_events_count", 0)
            },
            "recommendations": recommendations,
            "actions": [
                "POST /api/sentiment/cleanup - Manueller Cleanup",
                "POST /api/sentiment/optimize - Speicheroptimierung",
                "GET /api/sentiment/stats - Detaillierte Statistiken"
            ]
        }
        
    except Exception as e:
        logger.error(f"Fehler bei Health-Check: {e}")
        raise HTTPException(status_code=500, detail=f"Health-Check fehlgeschlagen: {e}")
