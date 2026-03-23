"""
kimi — Kimi K2.5 API Client (256K Kontext)
Fallback für Texte die DeepSeek (128K) übersteigen.
"""
import httpx
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

KIMI_MODEL = "moonshot-v1-128k"   # 128K Standard
KIMI_URL   = "https://api.moonshot.cn/v1/chat/completions"


async def call_kimi(
    system_prompt: str,
    user_prompt: str,
    model: str = KIMI_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """
    Ruft Kimi K2.5 API auf.
    Fallback auf DeepSeek wenn kein API-Key.
    """
    if not settings.kimi_api_key:
        logger.debug(
            "Kimi API Key nicht gesetzt — "
            "Fallback DeepSeek"
        )
        from backend.app.analysis.deepseek import (
            call_deepseek,
        )
        return await call_deepseek(
            system_prompt,
            user_prompt[:100_000],
            model="deepseek-chat",
        )

    try:
        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            resp = await client.post(
                KIMI_URL,
                headers={
                    "Authorization": (
                        f"Bearer {settings.kimi_api_key}"
                    ),
                    "Content-Type": "application/json",
                },
                json={
                    "model":       model,
                    "messages": [
                        {
                            "role":    "system",
                            "content": system_prompt,
                        },
                        {
                            "role":    "user",
                            "content": user_prompt,
                        },
                    ],
                    "temperature": temperature,
                    "max_tokens":  max_tokens,
                },
            )

            if resp.status_code == 429:
                logger.warning("Kimi Rate Limit")
                from backend.app.analysis.deepseek\
                    import call_deepseek
                return await call_deepseek(
                    system_prompt,
                    user_prompt[:100_000],
                )

            resp.raise_for_status()
            data = resp.json()
            content = (
                data["choices"][0]["message"]["content"]
            )
            usage = data.get("usage", {})
            logger.info(
                f"Kimi OK: "
                f"{usage.get('total_tokens','?')} tokens"
            )
            return content or ""

    except Exception as e:
        logger.warning(
            f"Kimi Fehler: {e} — Fallback DeepSeek"
        )
        from backend.app.analysis.deepseek import (
            call_deepseek,
        )
        return await call_deepseek(
            system_prompt,
            user_prompt[:100_000],
        )
