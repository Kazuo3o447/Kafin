import httpx
import yaml
import os
import asyncio
from backend.app.config import settings
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Load api config
CONFIG_YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "config", "apis.yaml")

# Modulweiter HTTP-Client — einmal erstellt, wiederverwendet
_http_client: httpx.AsyncClient | None = None

def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=300.0)
    return _http_client

def _load_deepseek_config():
    with open(CONFIG_YAML_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config.get("deepseek", {})

async def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    if settings.use_mock_data:
        logger.info("[MOCK] DeepSeek called via use_mock_data")
        return "MOCK_REPORT: Da use_mock_data aktiv ist, wird kein echter Request an DeepSeek gesendet.\nDies ist eine Platzhalter-Antwort."

    configs = _load_deepseek_config()
    api_key = settings.deepseek_api_key
    
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        return "ERROR: DEEPSEEK_API_KEY is missing."

    if not model:
        model = configs.get("model", "deepseek-chat")
    base_url = configs.get("base_url", "https://api.deepseek.com/1")
    if not max_tokens:
        max_tokens = configs.get("max_tokens", 2000)
    if model == "deepseek-chat" and temperature is None:
        temperature = configs.get("temperature", 0.7)
    if model == "deepseek-reasoner":
        temperature = 0.0

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
        "max_tokens": max_tokens,
        "stream": False,
    }

    # very simple retry backoff
    for attempt in range(3):
        try:
            client = _get_http_client()
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            # Check for HTTP errors and log response body if available
            if response.status_code != 200:
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text
                logger.error(f"DeepSeek API Error (Status {response.status_code}): {error_detail}")
            
            response.raise_for_status()
            data = response.json()
            
            # Logging limits & tokens
            usage = data.get("usage", {})
            input_tok  = usage.get("prompt_tokens", 0)
            output_tok = usage.get("completion_tokens", 0)
            logger.info(
                f"DeepSeek [{model}] "
                f"in={input_tok} out={output_tok} tokens"
            )

            # Usage tracken
            try:
                from backend.app.analysis.usage_tracker import (
                    track_call
                )
                await track_call(
                    api_name="deepseek",
                    model=model,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                )
            except Exception as e:
                logger.debug(f"Usage tracking Fehler: {e}")

            message = data["choices"][0]["message"]
            return message.get("content", "")

        except Exception as e:
            logger.warning(f"DeepSeek call failed (attempt {attempt+1}): {str(e)}")
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
            
    logger.error("DeepSeek call failed after 3 attempts.")
    return ""

async def call_deepseek_chat(
    system_prompt: str,
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> str:
    """
    Multi-Turn Variante. messages = [{"role": "user"|"assistant", "content": str}, ...]
    system_prompt wird als {"role": "system"} vorangestellt.
    max_tokens bewusst niedrig (1024) — Chat-Antworten sollen knapp sein.
    """
    if settings.use_mock_data:
        return "MOCK: Chat-Antwort nicht verfügbar im Mock-Modus."

    configs = _load_deepseek_config()
    api_key = settings.deepseek_api_key
    if not api_key:
        return "ERROR: DEEPSEEK_API_KEY fehlt."

    base_url = configs.get("base_url", "https://api.deepseek.com/1")

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    payload = {
        "model": model,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            client = _get_http_client()
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            try:
                from backend.app.analysis.usage_tracker import track_call
                await track_call(
                    api_name="deepseek",
                    model=model,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                )
            except Exception:
                pass

            return data["choices"][0]["message"].get("content", "")
        except Exception as e:
            logger.warning(f"call_deepseek_chat attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2 ** attempt)

    return "Fehler: DeepSeek nicht erreichbar."
