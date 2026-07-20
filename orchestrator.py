"""Phase-2 static tool orchestration (pre-TF-Agent rule-based routing).

Flow: detect image intent → GLM refines the art prompt → image service generates
→ the caller attaches the media URL to the chat response. Phase 3 replaces the
rule check with the TF-Agents RL policy; the interface stays the same.
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from . import agent_service, glm, image_service, sandbox_service, video_service
from .config import get_settings
from .models import MediaAsset, RoutingLog

settings = get_settings()


# ---------------- Phase 3: central routing (TF-Agents / rule policy) ----------------

def route_request(
    db: Session,
    *,
    user_id: int,
    user_text: str,
    conversation_len: int = 0,
    quota_remaining: int | None = None,
    explicit: dict | None = None,
) -> dict:
    """Single routing decision used by the console and /v1 endpoints.

    Delegates to the TF-Agents policy when a trained artifact is deployed,
    otherwise the rule-based policy, and logs the decision for future training.
    """
    from sqlalchemy import func

    from .models import UsageRecord

    user_total = db.query(func.count(UsageRecord.id)).filter(UsageRecord.user_id == user_id).scalar() or 0
    decision = agent_service.choose_action(
        user_text=user_text,
        conversation_len=conversation_len,
        quota_remaining=quota_remaining,
        user_total_requests=int(user_total),
        explicit=explicit or {},
    )
    db.add(
        RoutingLog(
            user_id=user_id,
            action=decision["action"],
            policy=decision["policy"],
            reason=decision["reason"],
            self_reflect=decision["self_reflect"],
        )
    )
    db.commit()
    return decision


async def refine_art_prompt(user_text: str) -> str:
    """Use GLM to turn a user request into a tight text-to-image prompt."""
    try:
        data = await glm.chat_completion(
            {
                "model": glm.resolve_model("nexus-chat"),
                "messages": [
                    {"role": "system", "content": image_service.REFINE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "max_tokens": 150,
                "temperature": 0.8,
            }
        )
        refined = (data["choices"][0]["message"]["content"] or "").strip().strip('"')
        return refined[:600] or user_text[:600]
    except Exception:
        return user_text[:600]


async def run_image_tool(
    db: Session,
    *,
    user_id: int,
    api_key_id: int | None,
    user_text: str,
    size: str = "1024x1024",
) -> dict:
    """Refine prompt, generate image, persist asset. Returns asset info dict."""
    refined = await refine_art_prompt(user_text)
    filename, url = await image_service.generate_image(refined, size=size)
    asset = MediaAsset(
        user_id=user_id,
        api_key_id=api_key_id,
        kind="image",
        prompt=refined,
        filename=filename,
        url=url,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "url": asset.url,
        "prompt": refined,
        "original_request": user_text,
        "markdown": f"![{refined[:80]}]({asset.url})",
    }


async def refine_video_prompt(user_text: str) -> str:
    """Use GLM to turn a user request into a tight text-to-video prompt."""
    try:
        data = await glm.chat_completion(
            {
                "model": glm.resolve_model("nexus-chat"),
                "messages": [
                    {"role": "system", "content": video_service.REFINE_VIDEO_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "max_tokens": 150,
                "temperature": 0.8,
            }
        )
        refined = (data["choices"][0]["message"]["content"] or "").strip().strip('"')
        return refined[:600] or user_text[:600]
    except Exception:
        return user_text[:600]


async def run_video_tool(
    db: Session,
    *,
    user_id: int,
    api_key_id: int | None,
    user_text: str,
) -> dict:
    """Refine prompt, generate MP4, persist asset. Returns asset info dict."""
    refined = await refine_video_prompt(user_text)
    filename, url = await video_service.generate_video(refined)
    asset = MediaAsset(
        user_id=user_id,
        api_key_id=api_key_id,
        kind="video",
        prompt=refined,
        filename=filename,
        url=url,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    # The console renders .mp4 image-markdown as a <video> player.
    return {
        "id": asset.id,
        "url": asset.url,
        "prompt": refined,
        "original_request": user_text,
        "markdown": f"![🎬 {refined[:70]}]({asset.url})",
    }


# ---------------- Phase 5: code generation → sandbox → self-fix loop ----------------

CODEGEN_SYSTEM = (
    "You are NexusAI Code Runner. The user will describe a task. Write a complete, "
    "runnable {lang} program that performs it and prints results with print(). "
    "If the task involves plotting, save figures as PNG files (e.g. plot.png) in the "
    "current directory. Output ONLY code inside one fenced code block — no prose."
)

FIX_SYSTEM = (
    "The following {lang} program was run in a sandbox and failed or produced wrong "
    "output. Fix it. Output ONLY the corrected code inside one fenced code block — no prose.\n\n"
    "PROGRAM:\n{code}\n\nSANDBOX STDERR/OUTPUT:\n{error}"
)

import re as _re

_CODE_BLOCK_RE = _re.compile(r"```(?:\w+)?\n(.*?)```", _re.DOTALL)


def _extract_code(text: str) -> str:
    m = _CODE_BLOCK_RE.search(text or "")
    return (m.group(1) if m else text or "").strip()


async def run_code_tool(
    db: Session,
    *,
    user_id: int,
    api_key_id: int | None,
    user_text: str,
    language: str = "python",
    status_cb: Callable[[str], None] | None = None,
) -> dict:
    """GLM generates code → sandbox executes → on failure feed logs back to GLM
    and retry (up to sandbox_max_attempts). Returns code, runs, final result."""
    lang = "python" if language.lower() in ("python", "py") else "javascript"

    async def _llm(messages: list[dict]) -> str:
        data = await glm.chat_completion(
            {
                "model": glm.resolve_model("nexus-code"),
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.3,
            }
        )
        return data["choices"][0]["message"]["content"] or ""

    # 1) Generate the program.
    raw = await _llm([
        {"role": "system", "content": CODEGEN_SYSTEM.format(lang=lang)},
        {"role": "user", "content": user_text},
    ])
    code = _extract_code(raw)

    # 2) Execute / self-fix loop.
    runs: list[dict] = []
    attempts = max(1, settings.sandbox_max_attempts)
    result: dict | None = None
    for attempt in range(1, attempts + 1):
        if status_cb:
            status_cb(f"Running code (attempt {attempt}/{attempts})…")
        result = await sandbox_service.execute_code(code, lang)
        runs.append({"attempt": attempt, "result": result, "code": code})
        if result["success"]:
            break
        if attempt < attempts:
            if status_cb:
                status_cb(f"Fixing error (attempt {attempt} failed)…")
            err = (result["stderr"] or result["stdout"] or "unknown error")[:1500]
            raw = await _llm([
                {"role": "system", "content": FIX_SYSTEM.format(lang=lang, code=code, error=err)},
                {"role": "user", "content": f"Original task: {user_text}"},
            ])
            code = _extract_code(raw)

    assert result is not None
    return {
        "code": code,
        "language": lang,
        "runs": runs,
        "result": result,
        "attempts_used": len(runs),
    }
