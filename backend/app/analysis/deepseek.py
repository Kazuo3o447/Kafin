import httpx
import yaml
import os
import asyncio
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Load api config
CONFIG_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "apis.yaml")

def _load_deepseek_config():
    with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config.get("deepseek", {})

async def call_deepseek(system_prompt: str, user_prompt: str) -> str:
    if settings.use_mock_data:
        logger.info("[MOCK] DeepSeek called via use_mock_data")
        return "MOCK_REPORT: Da use_mock_data aktiv ist, wird kein echter Request an DeepSeek gesendet.\nDies ist eine Platzhalter-Antwort."

    configs = _load_deepseek_config()
    api_key = settings.deepseek_api_key
    
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        return "ERROR: DEEPSEEK_API_KEY is missing."

    model = configs.get("model", "deepseek-chat")
    base_url = configs.get("base_url", "https://api.deepseek.com/1")
    max_tokens = configs.get("max_tokens", 2000)
    temperature = configs.get("temperature", 0.7)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    # very simple retry backoff
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # Logging limits & tokens
                usage = data.get("usage", {})
                logger.info(f"DeepSeek success. Tokens: {usage.get('total_tokens', 'N/A')}")
                
                return data["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.warning(f"DeepSeek call failed (attempt {attempt+1}): {str(e)}")
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
            
    logger.error("DeepSeek call failed after 3 attempts.")
    return ""
