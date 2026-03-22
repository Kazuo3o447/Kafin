# Groq API Documentation

## Overview
Groq wird für die News-Extraktion in Kafin eingesetzt, um schnelle Stichpunkt-Extraktion aus Finanznachrichten zu ermöglichen.

## Modell
- **Modell**: `llama-3.1-8b-instant`
- **Latenz**: ~200ms (10-50x schneller als DeepSeek Chat)
- **Kosten**: Kostenlos (Free Tier: ~14.400 Requests/Tag)
- **Use Case**: Strukturierte JSON-Extraktion, kurze Texte

## Konfiguration

### Environment Variable
```bash
GROQ_API_KEY=gsk_...
```

### Settings
In `backend/app/config.py`:
```python
groq_api_key: str = ""
```

## API Client

### Datei
`backend/app/analysis/groq.py`

### Hauptfunktion
```python
async def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.1-8b-instant",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str
```

### Features
- **Automatischer Fallback** auf DeepSeek bei:
  - Fehlender `GROQ_API_KEY`
  - HTTP 429 (Rate Limit)
  - HTTP Fehlern (non-200)
  - Timeout (20s)
  - Allgemeinen Exceptions

### Rate Limits
- **News-Extraktion**: 20 Calls/Ticker/Stunde (erhöht von 5/h)
- **Free Tier**: 14.400 Requests/Tag

## Verwendung in der Pipeline

### News-Extraktion
In `backend/app/data/news_processor.py`:
```python
from backend.app.analysis.groq import call_groq

# Statt DeepSeek für Bullet-Point-Extraktion
result = await call_groq(system_prompt, user_prompt)
```

### KI-Pipeline Stufen
1. **FinBERT** (lokal) - Sentiment-Filter
2. **Groq** llama-3.1-8b-instant - News-Extraktion (+ Fallback)
3. **DeepSeek** Chat - komplexe Analyse
4. **Kimi** K2.5 - Earnings-Transkripte
5. **DeepSeek** Reasoner - Audit-Reports

## Testing

### Test-Skript
`backend/tests/test_groq.py`

### Tests
```bash
# Mit gesetztem GROQ_API_KEY
python backend/tests/test_groq.py

# Erwartete Ausgabe:
# Test 1: Einfache Verbindung... ✓ Antwort: OK
# Test 2: News-Extraktion (JSON)... ✓ JSON valide: 3 Stichpunkte
# Test 3: Fallback prüfen... ✓ Fallback aktiv: True
# ✅ Alle Tests bestanden.
```

## Logging

### Log-Level
- **Debug**: `Groq [model] OK — X tokens`
- **Warning**: `Groq Rate Limit/HTTP/Timeout/Fehler — Fallback DeepSeek`

### Beispiel
```
2026-03-22 16:54:13,737 [INFO] httpx: HTTP Request: POST https://api.groq.com/openai/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-22 16:54:14,129 [DEBUG] Groq [llama-3.1-8b-instant] OK — 87 tokens
```

## Fehlerbehandlung

### Common Errors
1. **401 Unauthorized**: API Key falsch oder nicht gesetzt
   - Lösung: `GROQ_API_KEY` in `.env` prüfen
2. **429 Rate Limit**: Zu viele Requests
   - Lösung: Automatischer Fallback auf DeepSeek
3. **Timeout**: Langsame Antwort
   - Lösung: Automatischer Fallback auf DeepSeek

### Fallback-Strategie
Bei jedem Fehler wird automatisch auf `call_deepseek()` zurückgegriffen, ohne die News-Pipeline zu unterbrechen.

## API Endpunkt

### URL
```
https://api.groq.com/openai/v1/chat/completions
```

### Headers
```json
{
  "Authorization": "Bearer gsk_...",
  "Content-Type": "application/json"
}
```

### Payload
```json
{
  "model": "llama-3.1-8b-instant",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.1,
  "max_tokens": 512
}
```

## Performance

### Vergleiche
- **Groq**: ~200ms Latenz
- **DeepSeek**: ~2-5s Latenz
- **Speedup**: 10-25x schneller

### Kosten
- **Groq**: Kostenlos (Free Tier)
- **DeepSeek**: Kostenpflichtig
- **Ersparnis**: 100% bei News-Extraktion

## Sicherheit

### Key Management
- **NIE** Keys in Git committen
- **Immer** in `.env` lokal speichern
- **Docker** liest `.env` via `env_file` in `docker-compose.yml`

### Best Practices
- Key regelmäßig rotieren (falls erforderlich)
- Bei Verdacht auf Compromise sofort neuen Key generieren
- Nur Free Tier nutzen (keine Kreditkarte erforderlich)
