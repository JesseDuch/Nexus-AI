"""Async wrapper around the Zhipu GLM OpenAI-compatible upstream API."""
from collections.abc import AsyncGenerator

import httpx

from .config import get_settings

settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

# Public model aliases -> upstream GLM models
MODEL_MAP = {
    "nexus-chat": settings.glm_default_model,
    "nexus-code": settings.glm_default_model,
    "glm-4-flash": "glm-4-flash",
    "glm-4-flashx": "glm-4-flashx",
    "glm-4-air": "glm-4-air",
    "glm-4-airx": "glm-4-airx",
    "glm-4-plus": "glm-4-plus",
    "glm-4-long": "glm-4-long",
}


def resolve_model(public_name: str | None) -> str:
    if not public_name:
        return settings.glm_default_model
    return MODEL_MAP.get(public_name, settings.glm_default_model)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.glm_api_key}",
        "Content-Type": "application/json",
    }


def _url(path: str) -> str:
    return f"{settings.glm_base_url.rstrip('/')}{path}"


async def chat_completion(payload: dict) -> dict:
    """Non-streaming chat completion against GLM."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url("/chat/completions"), json=payload, headers=_headers())
        data = resp.json()
        if resp.status_code >= 400:
            message = data.get("error", {}).get("message") if isinstance(data, dict) else None
            raise GlmUpstreamError(resp.status_code, message or resp.text[:300])
        return data


async def chat_completion_stream(payload: dict) -> AsyncGenerator[str, None]:
    """Streaming chat completion — yields raw SSE `data:` lines from GLM."""
    payload = {**payload, "stream": True, "stream_options": {"include_usage": True}}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST", _url("/chat/completions"), json=payload, headers=_headers()
        ) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode(errors="replace")[:500]
                raise GlmUpstreamError(resp.status_code, body)
            async for line in resp.aiter_lines():
                if line.strip():
                    yield line


class GlmUpstreamError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GLM upstream {status_code}: {message}")
