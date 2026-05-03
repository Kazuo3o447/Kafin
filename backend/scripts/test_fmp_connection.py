"""
test_fmp_connection.py — Testskript für die Financial Modeling Prep (FMP) API Anbindung

Dieses Skript prüft, ob der in der `.env` angegebene FMP_API_KEY korrekt ist,
indem es das Unternehmensprofil für Apple (AAPL) abruft.

API: FMP Company Profile Lookup
"""

import os
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    api_key = os.environ.get("FMP_API_KEY")
    
    if not api_key or api_key == "mock":
        print("FEHLER: Kein gültiger FMP_API_KEY in der .env gefunden.")
        return

    print(f"Teste FMP Verbindung mit Key: {api_key[:5]}...{api_key[-5:]}")
    
    url = f"https://financialmodelingprep.com/stable/search-symbol?query=AAPL&apikey={api_key}"
    
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response Body: {response.text}")
                
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                print(f"ERFOLG! Verbindung zu FMP stabil. Daten für AAPL abgerufen.")
                print(f"Beispiel-Daten (AAPL): Name: {data[0].get('companyName')}, Sektor: {data[0].get('sector')}, Preis: ${data[0].get('price')}")
            else:
                print("WARNUNG: Verbindung erfolgreich, aber keine oder unerwartete Daten zurückgegeben.")
                print(f"Antwort: {data}")
                
    except Exception as e:
        print(f"\n[FEHLER] Verbindung zu FMP fehlgeschlagen.")
        print(f"Details: {e}")

if __name__ == "__main__":
    main()
