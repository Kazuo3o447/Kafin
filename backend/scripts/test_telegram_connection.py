"""
test_telegram_connection.py — Testskript für die Telegram API Anbindung

Dieses Skript prüft, ob der in der `.env` angegebene TELEGRAM_BOT_TOKEN korrekt ist,
indem es die /getMe Funktion der Telegram API aufruft.

API: Telegram Bot API
"""

import os
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not bot_token or bot_token == "mock" or bot_token == "":
        print("FEHLER: Kein gültiger TELEGRAM_BOT_TOKEN in der .env gefunden.")
        return

    print(f"Teste Telegram Verbindung mit Bot-Token: {bot_token[:5]}...{bot_token[-5:]}")
    
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response Body: {response.text}")
                
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                result = data.get("result", {})
                print(f"ERFOLG! Verbindung zu Telegram stabil.")
                print(f"Bot-Profil: Name: {result.get('first_name')}, Username: @{result.get('username')}")
                
                # Check for Chat ID
                chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                if not chat_id or chat_id == "":
                    print("\nHINWEIS: TELEGRAM_CHAT_ID fehlt in der .env")
                    print("Um herauszufinden, wie deine Chat-ID lautet:")
                    print(f"1. Öffne Telegram und suche nach @{result.get('username')}")
                    print("2. Sende dem Bot eine Nachricht (z. B. 'Hallo')")
                    print("3. Rufe danach folgende URL im Browser auf (oder per curl):")
                    print(f"   https://api.telegram.org/bot{bot_token}/getUpdates")
                    print("4. Kopiere die 'id' unter 'chat', trag sie in die .env als TELEGRAM_CHAT_ID ein und starte das Backend neu.")
            else:
                print("WARNUNG: Verbindung erfolgreich, aber API meldet nicht 'ok'.")
                print(f"Antwort: {data}")
                
    except Exception as e:
        print(f"\n[FEHLER] Verbindung zu Telegram fehlgeschlagen.")
        print(f"Details: {e}")

if __name__ == "__main__":
    main()
