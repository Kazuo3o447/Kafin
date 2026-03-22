"""
Groq API Client für schnelle Text-Extraktion.
Kostenloser Tier: ~14.400 Requests/Tag bei Llama 3.
Fallback auf DeepSeek wenn Groq nicht konfiguriert.
"""
import os
import httpx
from backend.app.logger import get_logger

logger = get_logger(__name__)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"


async def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str = GROQ_MODEL,
) -> str:
    """
    Ruft Groq API auf. Fallback auf DeepSeek wenn
    GROQ_API_KEY nicht gesetzt.
    """
    if not GROQ_API_KEY:
        from backend.app.analysis.deepseek import call_deepseek
        logger.debug("Groq nicht konfiguriert — Fallback DeepSeek")
        return await call_deepseek(system_prompt, user_prompt)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system",
                         "content": system_prompt},
                        {"role": "user",
                         "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (
                data["choices"][0]["message"]["content"]
                or ""
            )
    except Exception as e:
        logger.warning(
            f"Groq API Fehler: {e} — Fallback DeepSeek"
        )
        from backend.app.analysis.deepseek import call_deepseek
        return await call_deepseek(system_prompt, user_prompt)
