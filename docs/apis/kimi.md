# Kimi / Moonshot AI API

Base-URL: `https://api.moonshot.ai/v1`
Auth: Header `Authorization: Bearer {KIMI_API_KEY}`
Modelle: `moonshot-v1-auto` (automatische Kontextauswahl), `kimi-k2.5` (neuestes)
Kontext: Bis 256K Tokens (K2.5)
Docs: https://platform.moonshot.ai/docs/api/chat
API-Format: OpenAI-kompatibel

## Genutzter Endpoint

### Chat Completions
POST /chat/completions

Request-Body (identisch mit OpenAI-Format):
```json
{
    "model": "moonshot-v1-auto",
    "messages": [
        {"role": "system", "content": "System-Prompt"},
        {"role": "user", "content": "User-Prompt (kann sehr lang sein, bis 256K)"}
    ],
    "temperature": 0.6,
    "max_tokens": 8192
}
```

Response (identisch mit OpenAI-Format):
```json
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "Antwort-Text"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 12000,
        "completion_tokens": 2000,
        "total_tokens": 14000
    }
}
```

## Besonderheiten
- Temperature nur 0-1 (nicht 0-2 wie bei OpenAI)
- Empfohlene Temperature: 0.6 für Reasoning, 0.3 für strukturierte Analysen
- 256K Kontext → Ideal für ganze Earnings-Call-Transkripte
- OpenAI Python SDK funktioniert direkt: base_url="https://api.moonshot.ai/v1"

## Einsatz in Kafin
- Stufe 2 der KI-Kaskade: Tiefenanalyse von Earnings-Transkripten
- Nur für Audit-Reports (5-8 pro Woche), nicht für Massen-Screening
- Pricing: $0.60/M Input, $2.50/M Output

## Python-Beispiel
```python
import httpx

headers = {
    "Authorization": f"Bearer {KIMI_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "moonshot-v1-auto",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript_text}  # Kann 50K+ Tokens sein
    ],
    "temperature": 0.6,
    "max_tokens": 8192
}
response = await client.post(
    "https://api.moonshot.ai/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=60.0  # Längerer Timeout für große Kontexte
)
text = response.json()["choices"][0]["message"]["content"]
```
