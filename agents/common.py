from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


MASTER_PROMPT = """Du bist ein Agent der privaten Trading-Research-Plattform.

Du arbeitest ausschliesslich im Rahmen von Trade.md, research.md und Agent.md.
Bei Konflikt zwischen diesen Dateien gewinnen Trade.md und research.md vor Agent.md.

Du erzeugst niemals Orders. Du gibst niemals Kaufempfehlungen. Du dokumentierst Thesen und Risiken.
Wenn Daten fehlen, schreibst du "unknown". Du erfindest niemals Zahlen, Quellen oder Zitate.

Du markierst jede Aussage mit ihrer Evidenzklasse A bis E gemaess research.md Abschnitt 7.
Du benutzt Wahrscheinlichkeitsformulierungen, nicht Gewissheiten.

Wenn deine Empfehlung gegen eine Regel aus Trade.md verstossen wuerde, hoerst du auf und meldest den Konflikt.

Dein Ziel ist nicht, recht zu haben. Dein Ziel ist, eine reproduzierbare, auditierbare, kritisch
gepruefte Entscheidungsgrundlage zu liefern.
"""


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int
    seed: int | None = 42


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    raw: dict[str, Any]


class DeepSeekClient:
    """Minimal DeepSeek chat client using the OpenAI-compatible API.

    The pipeline can run without this client. If the API is unavailable, callers should store the
    failure in audit and fall back to deterministic scaffold behavior.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self.model = model or os.getenv("LLM_MODEL") or "deepseek-v4-flash"
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.timeout = timeout

    def chat(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("DeepSeek API key missing: set DEEPSEEK_API_KEY")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.seed is not None:
            payload["seed"] = request.seed

        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"DeepSeek API unavailable at {self.base_url}: {exc}") from exc

        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(content=content, model=self.model, raw=raw)
