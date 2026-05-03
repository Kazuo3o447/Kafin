# DeepSeek API

Base-URL: `https://api.deepseek.com` (oder `https://api.deepseek.com/v1` für OpenAI-Kompatibilität)
Auth: Header `Authorization: Bearer {DEEPSEEK_API_KEY}`
Modell: `deepseek-chat` (DeepSeek-V3.2, 128K Kontext)
Docs: https://api-docs.deepseek.com/
Pricing: $0.28/M Input-Tokens, $0.42/M Output-Tokens (Stand März 2026)

## Konfiguration
- DEEPSEEK_API_KEY: sk-13a56192cfd74ba6b1b6bfc68d4555ff

## Genutzter Endpoint

### Chat Completions
POST /chat/completions

Request-Body:
```json
{
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "System-Prompt"},
        {"role": "user", "content": "User-Prompt"}
    ],
    "temperature": 0.3,
    "max_tokens": 4096,
    "stream": false
}
```

Response:
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
        "prompt_tokens": 150,
        "completion_tokens": 500,
        "total_tokens": 650
    }
}
```

## Wichtige Parameter
- temperature: 0.3 für konsistente Analysen (nicht zu kreativ)
- max_tokens: 4096 für Reports
- stream: false (wir brauchen kein Streaming)

## Für JSON-Output
Im System-Prompt angeben: "Antworte NUR mit validem JSON, ohne Markdown-Backticks."
Alternativ: `response_format: {"type": "json_object"}` im Request

## Fehler-Handling
- 429: Rate Limit → Retry mit Backoff
- 401: Ungültiger Key
- 500/502/503: Server-Fehler → Retry

## Python-Beispiel
```python
import httpx

headers = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.3,
    "max_tokens": 4096
}
response = await client.post(
    "https://api.deepseek.com/chat/completions",
    headers=headers,
    json=payload
)
text = response.json()["choices"][0]["message"]["content"]
```
