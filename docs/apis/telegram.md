# Telegram Bot API

Base-URL: `https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}`
Auth: Im URL-Pfad enthalten
Rate-Limit: ~30 Messages per second (broadcasting)
Docs: https://core.telegram.org/bots/api

## Konfiguration
- TELEGRAM_BOT_TOKEN: 8625880380:AAH3Jcg7dq40nODDoGEUqxLaUR0VWTXhKUU
- TELEGRAM_CHAT_ID: (Noch leer - muss über `/getUpdates` oder Chat generiert werden)

## Genutzter Endpoint

### Get Me (Bot Info)
GET /getMe

Response:
- ok (bool): true
- result (object): Bot-Profil (id, is_bot, first_name, username)

### Send Message
POST /sendMessage

Request-Body:
```json
{
    "chat_id": "DEINE_CHAT_ID",
    "text": "Nachrichtentext",
    "parse_mode": "MarkdownV2"
}
```

## Python-Beispiel
```python
import httpx

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": TELEGRAM_CHAT_ID,
    "text": "Kafin: Testnachricht"
}
response = await client.post(url, json=payload)
```
