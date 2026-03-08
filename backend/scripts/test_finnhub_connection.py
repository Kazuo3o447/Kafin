"""
test_finnhub.py — Testskript für die Finnhub API Anbindung

Dieses Skript prüft, ob der in der `.env` angegebene FINNHUB_API_KEY korrekt ist,
indem es eine einfache Abfrage (Symbol Lookup für Apple) durchführt.

API: Finnhub Stock Lookup
"""

import os
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    api_key = os.environ.get("FINNHUB_API_KEY")
    
    if not api_key or api_key == "mock":
        print("FEHLER: Kein gültiger FINNHUB_API_KEY in der .env gefunden.")
        return

    print(f"Teste Finnhub Verbindung mit Key: {api_key[:5]}...{api_key[-5:]}")
    
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={api_key}"
    
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url)
            print(f"Status Code: {response.status_code}")
            if response.status_code != 200:
                print(f"Response Body: {response.text}")
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                print(f"ERFOLG! Verbindung zu Finnhub stabil. {len(data)} Symbole gefunden.")
                # Zeige einen Ticker als Beweis
                for item in data:
                    if item.get("symbol") == "AAPL":
                        print(f"Beispiel-Daten (AAPL): {item.get('description')}")
                        break
            elif isinstance(data, dict):
                print(f"ERFOLG! Antwort erhalten: {data}")
            else:
                print("WARNUNG: Verbindung erfolgreich, aber ungewöhnliches Datenformat oder leer.")
                
    except Exception as e:
        print(f"\n[FEHLER] Verbindung zu Finnhub fehlgeschlagen.")
        print(f"Details: {e}")

if __name__ == "__main__":
    main()
