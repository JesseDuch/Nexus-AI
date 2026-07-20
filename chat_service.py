"""Core chat orchestration shared by the public /v1 endpoint and the web console.

Normalizes platform requests -> GLM upstream payload, and GLM output ->
OpenAI-standard JSON (both streaming SSE and unary).
"""
import json
import time
import uuid
from collections.abc import AsyncGenerator, Callable

from . import glm
from .schemas import ChatCompletionRequest

CODE_SYSTEM_PROMPT = (
    "You are NexusAI Code, an expert programming assistant. Answer with correct, "
    "runnable code in fenced markdown code blocks, brief explanations, and note "
    "edge cases or complexity where relevant."
)


def estimate_tokens(text: str) -> int:
    """Rough heuristic when upstream usage stats are unavailable."""
    return max(1, len(text) // 4) if text else 0


def build_glm_payload(req: ChatCompletionRequest) -> dict:
    messages = [m.model_dump(exclude_none=True) for m in req.messages]

    # Roadmap extension: tools=["code"] biases the model toward code generation.
    if req.tools and any(t == "code" or (isinstance(t, dict) and t.get("type") == "code") for t in req.tools):
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": CODE_SYSTEM_PROMPT})

    payload: dict = {
        "model": glm.resolve_model(req.model),
        "messages": messages,
    }
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    if req.top_p is not None:
        payload["top_p"] = req.top_p
    if req.max_tokens is not None:
        payload["max_tokens"] = req.max_tokens
    if req.stop is not None:
        payload["stop"] = req.stop
    return payload


def public_model_name(req_model: str | None) -> str:
    return req_model or "nexus-chat"


async def run_non_stream(req: ChatCompletionRequest) -> tuple[dict, dict, str]:
    """Returns (openai_response, usage, assistant_text)."""
    payload = build_glm_payload(req)
    upstream = await glm.chat_completion(payload)

    usage = upstream.get("usage") or {}
    text = ""
    choices = upstream.get("choices") or []
    if choices:
        text = (choices[0].get("message") or {}).get("content") or ""

    if not usage:
        prompt_text = "".join((m.content or "") if isinstance(m.content, str) else "" for m in req.messages)
        usage = {
            "prompt_tokens": estimate_tokens(prompt_text),
            "completion_tokens": estimate_tokens(text),
            "total_tokens": 0,
        }
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

    # Normalize id/object to OpenAI standard regardless of upstream shape.
    response = {
        "id": upstream.get("id") or f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": upstream.get("created") or int(time.time()),
        "model": public_model_name(req.model),
        "choices": upstream.get("choices") or [],
        "usage": usage,
    }
    return response, usage, text


async def run_stream(
    req: ChatCompletionRequest,
    state: dict,
) -> AsyncGenerator[str, None]:
    """Yields SSE lines (`data: ...`) — passes GLM chunks through untouched,
    while recording accumulated text/usage into the caller-provided `state` dict
    (keys: text_parts, usage) so callers can persist them afterwards."""
    payload = build_glm_payload(req)
    state.setdefault("text_parts", [])
    state.setdefault("usage", None)

    async for line in glm.chat_completion_stream(payload):
        if line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            if data_str and data_str != "[DONE]":
                try:
                    chunk = json.loads(data_str)
                    if chunk.get("usage"):
                        state["usage"] = chunk["usage"]
                    for choice in chunk.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            state["text_parts"].append(delta)
                except json.JSONDecodeError:
                    pass
        yield line + "\n\n"

    if state["usage"] is None:
        prompt_text = "".join((m.content or "") if isinstance(m.content, str) else "" for m in req.messages)
        completion = estimate_tokens("".join(state["text_parts"]))
        state["usage"] = {
            "prompt_tokens": estimate_tokens(prompt_text),
            "completion_tokens": completion,
            "total_tokens": estimate_tokens(prompt_text) + completion,
        }
