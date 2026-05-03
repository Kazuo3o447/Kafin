"""
test_fred_connection.py — Testskript für die FRED API Anbindung

Dieses Skript prüft, ob der in der `.env` angegebene FRED_API_KEY korrekt ist,
indem es den aktuellen Stand des VIX (CBOE Volatility Index) abruft.

API: FRED Series Observations Lookup
"""

import os
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    api_key = os.environ.get("FRED_API_KEY")
    
    if not api_key or api_key == "mock":
        print("FEHLER: Kein gültiger FRED_API_KEY in der .env gefunden.")
        return

    print(f"Teste FRED Verbindung mit Key: {api_key[:5]}...{api_key[-5:]}")
    
    # URL für VIXCLS (VIX Index)
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "VIXCLS",
        "api_key": api_key,
        "sort_order": "desc",
        "limit": 1,
        "file_type": "json"
    }
    
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url, params=params)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response Body: {response.text}")
                
            response.raise_for_status()
            data = response.json()
            
            observations = data.get("observations", [])
            
            if observations and len(observations) > 0:
                print(f"ERFOLG! Verbindung zu FRED stabil.")
                print(f"Beispiel-Daten (VIX): Datum: {observations[0].get('date')}, Wert: {observations[0].get('value')}")
            else:
                print("WARNUNG: Verbindung erfolgreich, aber keine oder unerwartete Daten (observations array ist leer) zurückgegeben.")
                print(f"Antwort: {data}")
                
    except Exception as e:
        print(f"\n[FEHLER] Verbindung zu FRED fehlgeschlagen.")
        print(f"Details: {e}")

if __name__ == "__main__":
    main()
