"""
SentinelAI — OpenRouter AI Client
Configurable AI model client supporting streaming and non-streaming responses.
Model names come from environment variables ONLY - never hardcoded.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger("sentinel.ai.openrouter")

SYSTEM_PROMPT = """You are SentinelAI, an expert autonomous Site Reliability Engineer (SRE) with deep expertise in:
- Distributed systems failure analysis
- Root cause investigation methodology
- Infrastructure dependency mapping
- Incident post-mortem writing
- Business impact quantification

You analyze incidents systematically, cite evidence from logs and metrics, and provide actionable recommendations.
Always be precise, cite specific evidence, and express confidence levels."""


class OpenRouterClient:
    """
    Async OpenRouter API client.
    Supports: standard completion, streaming SSE, function calling.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://sentinelai.dev",
                "X-Title": "SentinelAI",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Standard (non-streaming) completion. Returns the response text."""
        model = model or settings.openrouter_default_model
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming completion - yields text chunks as they arrive.
        Use for SSE endpoints to show AI reasoning in real time.
        """
        model = model or settings.openrouter_default_model
        payload = {
            "model": model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    import json
                    data = json.loads(data_str)
                    delta = data["choices"][0]["delta"]
                    if content := delta.get("content"):
                        yield content
                except (KeyError, ValueError):
                    continue

    def _build_messages(
        self,
        messages: List[Dict],
        system_prompt: Optional[str] = None,
    ) -> List[Dict]:
        """Prepend system prompt to message list."""
        sys = system_prompt or SYSTEM_PROMPT
        return [{"role": "system", "content": sys}] + messages

    async def close(self) -> None:
        await self._client.aclose()


# Module-level singleton
_openrouter_client: OpenRouterClient | None = None


def get_openrouter() -> OpenRouterClient:
    """Return the global OpenRouter client (lazy init)."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client


async def close_openrouter() -> None:
    """Close the client on shutdown."""
    global _openrouter_client
    if _openrouter_client:
        await _openrouter_client.close()
        _openrouter_client = None
