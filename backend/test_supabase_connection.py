#!/usr/bin/env python3
"""
Test-Skript für Supabase-Verbindung und grundlegende Operationen.
"""

import asyncio
import sys
import os

# Backend-Pfad hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from backend.app.db import get_supabase_client
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

async def test_supabase_connection():
    """Testet die Supabase-Verbindung und grundlegende CRUD-Operationen."""
    print("=== Supabase Verbindungstest ===\n")
    
    # 1. Konfiguration prüfen
    print("1. Konfiguration:")
    print(f"   SUPABASE_URL: {settings.supabase_url}")
    print(f"   SUPABASE_KEY gesetzt: {'Ja' if settings.supabase_key else 'Nein'}")
    print(f"   use_mock_data: {settings.use_mock_data}")
    print()
    
    # 2. Client erstellen
    print("2. Client-Erstellung...")
    try:
        client = get_supabase_client()
        if client is None:
            print("   ❌ Client konnte nicht erstellt werden (siehe obige Fehler)")
            return False
        print("   ✅ Client erstellt")
    except Exception as e:
        print(f"   ❌ Client-Erstellung fehlgeschlagen: {e}")
        return False
    print()
    
    # 3. Test-Query: Tabellen auflisten
    print("3. Tabellen-Abfrage...")
    try:
        # Versuche die watchlist-Tabelle abzufragen (sollte existieren)
        response = client.table("watchlist").select("count", count="exact").execute()
        print(f"   ✅ watchlist-Tabelle erreichbar, Einträge: {response.count}")
    except Exception as e:
        print(f"   ❌ Tabellen-Abfrage fehlgeschlagen: {e}")
        return False
    print()
    
    # 4. Test-Insert (mit cleanup)
    print("4. Test-Insert & Delete...")
    test_ticker = "TEST_CONNECTION_CHECK"
    try:
        # Insert
        insert_data = {
            "ticker": test_ticker,
            "company_name": "Test Company",
            "sector": "Technology",
            "notes": "Test-Eintrag für Verbindungstest",
            "cross_signal_tickers": []
        }
        response = client.table("watchlist").insert(insert_data).execute()
        if response.data:
            print("   ✅ Insert erfolgreich")
        else:
            print("   ❌ Insert ohne Daten")
            return False
        
        # Delete (cleanup)
        response = client.table("watchlist").delete().eq("ticker", test_ticker).execute()
        if response.data:
            print("   ✅ Delete (Cleanup) erfolgreich")
        else:
            print("   ⚠️ Delete (Cleanup) ohne Daten")
        
    except Exception as e:
        print(f"   ❌ Insert/Delete Test fehlgeschlagen: {e}")
        return False
    print()
    
    # 5. Test-Select
    print("5. Test-Select...")
    try:
        response = client.table("watchlist").select("*").limit(1).execute()
        print(f"   ✅ Select erfolgreich, gefunden: {len(response.data)} Eintrag(e)")
        if response.data:
            print(f"      Beispiel: {response.data[0].get('ticker', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Select fehlgeschlagen: {e}")
        return False
    print()
    
    print("=== Test abgeschlossen ===")
    print("✅ Supabase-Verbindung steht und funktioniert zuverlässig!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_supabase_connection())
    sys.exit(0 if success else 1)
