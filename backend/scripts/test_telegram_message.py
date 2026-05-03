"""
test_telegram_message.py — Testskript zum Senden einer Telegram-Nachricht

Prüft, ob der Bot eine Nachricht an die konfigurierte TELEGRAM_CHAT_ID senden kann.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("FEHLER: Bot Token oder Chat ID fehlt.")
        return

    print(f"Sende Testnachricht an Chat ID: {chat_id}...")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🚀 *Kafin System-Check*\n\nDie Verbindung zum Telegram-Bot steht! Ich bin bereit für die Torpedo-Warnungen.",
        "parse_mode": "Markdown"
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            print("ERFOLG! Nachricht wurde gesendet. Prüfe dein Telegram!")
    except Exception as e:
        print(f"FEHLER: {e}")

if __name__ == "__main__":
    main()
