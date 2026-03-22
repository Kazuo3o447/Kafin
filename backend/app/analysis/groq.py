"""
Groq API Client — schnelle Inferenz für News-Extraktion.

Modell: llama-3.1-8b-instant
  - Kostenloser Tier: ~14.400 Requests/Tag
  - Latenz: ~200ms (10-50x schneller als DeepSeek Chat)
  - Ideal für: strukturierte JSON-Extraktion, kurze Texte

Fallback: DeepSeek Chat wenn GROQ_API_KEY nicht gesetzt.
"""
import httpx
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

GROQ_MODEL   = "llama-3.1-8b-instant"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"


async def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str = GROQ_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """
    Ruft Groq API auf.
    Automatischer Fallback auf DeepSeek wenn
    GROQ_API_KEY nicht gesetzt oder API-Fehler.
    """
    if not settings.groq_api_key:
        logger.debug(
            "GROQ_API_KEY nicht gesetzt — Fallback DeepSeek"
        )
        from backend.app.analysis.deepseek import call_deepseek
        return await call_deepseek(system_prompt, user_prompt)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens":  max_tokens,
                },
            )

            if resp.status_code == 429:
                logger.warning(
                    "Groq Rate Limit — Fallback DeepSeek"
                )
                from backend.app.analysis.deepseek import call_deepseek
                return await call_deepseek(system_prompt, user_prompt)

            if resp.status_code != 200:
                logger.warning(
                    f"Groq HTTP {resp.status_code} — Fallback DeepSeek"
                )
                from backend.app.analysis.deepseek import call_deepseek
                return await call_deepseek(system_prompt, user_prompt)

            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
            )
            logger.debug(
                f"Groq [{model}] OK — "
                f"{data.get('usage', {}).get('total_tokens', '?')} tokens"
            )
            return content or ""

    except httpx.TimeoutException:
        logger.warning("Groq Timeout — Fallback DeepSeek")
        from backend.app.analysis.deepseek import call_deepseek
        return await call_deepseek(system_prompt, user_prompt)

    except Exception as e:
        logger.warning(f"Groq Fehler: {e} — Fallback DeepSeek")
        from backend.app.analysis.deepseek import call_deepseek
        return await call_deepseek(system_prompt, user_prompt)
