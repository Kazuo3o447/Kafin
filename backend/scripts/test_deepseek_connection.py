"""
test_deepseek_connection.py — Testskript für die DeepSeek API Anbindung

Dieses Skript prüft, ob der in der `.env` angegebene DEEPSEEK_API_KEY korrekt ist,
indem es einen minimalen Chat-Completion Request ausführt ("Ping").

API: DeepSeek Chat Completions
"""

import os
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    
    if not api_key or api_key == "mock":
        print("FEHLER: Kein gültiger DEEPSEEK_API_KEY in der .env gefunden.")
        return

    print(f"Teste DeepSeek Verbindung mit Key: {api_key[:5]}...{api_key[-5:]}")
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Antworte nur mit 'PONG'."}
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, headers=headers, json=payload)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response Body: {response.text}")
                
            response.raise_for_status()
            data = response.json()
            
            choices = data.get("choices", [])
            
            if choices and len(choices) > 0:
                answer = choices[0].get("message", {}).get("content", "").strip()
                print(f"ERFOLG! Verbindung zu DeepSeek stabil.")
                print(f"Antwort vom Model (deepseek-chat): {answer}")
                print(f"Token-Verbrauch: {data.get('usage', {}).get('total_tokens')} total tokens")
            else:
                print("WARNUNG: Verbindung erfolgreich, aber keine Antwort im Response-Objekt gefunden.")
                print(f"Antwort: {data}")
                
    except Exception as e:
        print(f"\n[FEHLER] Verbindung zu DeepSeek fehlgeschlagen.")
        print(f"Details: {e}")

if __name__ == "__main__":
    main()
