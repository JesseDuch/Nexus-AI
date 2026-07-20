"""Image generation service — pluggable backend (roadmap 2.1).

Backends:
  • "cogview"  — Zhipu CogView via the GLM key (works out of the box)
  • "tf-local" — a TensorFlow Stable Diffusion HTTP service you deploy yourself
                 (set TF_IMAGE_URL; it must accept {"prompt","size"} and return
                 an image binary or {"url": ...})

Generated files are stored locally and served from /media/{filename} so the
public URL is permanent (upstream signed URLs expire).
"""
import re
import uuid
from pathlib import Path

import httpx

from .config import get_settings

settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
ALLOWED_SIZES = {"1024x1024", "768x1344", "1344x768"}


def media_dir() -> Path:
    d = Path(settings.media_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


class ImageBackendError(Exception):
    pass


async def generate_image(prompt: str, size: str = "1024x1024") -> tuple[str, str]:
    """Generate an image, persist it, return (filename, public_url_path)."""
    if size not in ALLOWED_SIZES:
        size = "1024x1024"
    backend = settings.image_backend.lower()
    if backend == "tf-local":
        content = await _generate_tf_local(prompt, size)
    else:
        content = await _generate_cogview(prompt, size)

    filename = f"img_{uuid.uuid4().hex[:16]}.png"
    (media_dir() / filename).write_bytes(content)
    return filename, f"/media/{filename}"


async def _generate_cogview(prompt: str, size: str) -> bytes:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{settings.glm_base_url.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {settings.glm_api_key}"},
            json={"model": settings.cogview_model, "prompt": prompt, "size": size},
        )
        data = resp.json()
        if resp.status_code >= 400:
            msg = data.get("error", {}).get("message", resp.text[:300]) if isinstance(data, dict) else resp.text[:300]
            raise ImageBackendError(f"CogView error ({resp.status_code}): {msg}")
        url = (data.get("data") or [{}])[0].get("url")
        if not url:
            raise ImageBackendError("CogView returned no image URL")
        img = await client.get(url)
        if img.status_code >= 400 or len(img.content) < 1000:
            raise ImageBackendError("Failed to download generated image")
        return img.content


async def _generate_tf_local(prompt: str, size: str) -> bytes:
    """Calls your own TensorFlow diffusion service (Phase-2 GPU worker)."""
    if not settings.tf_image_url:
        raise ImageBackendError("TF_IMAGE_URL is not configured for the tf-local backend")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(settings.tf_image_url, json={"prompt": prompt, "size": size})
        if resp.status_code >= 400:
            raise ImageBackendError(f"TF image service error ({resp.status_code}): {resp.text[:300]}")
        ctype = resp.headers.get("content-type", "")
        if ctype.startswith("image/"):
            return resp.content
        data = resp.json()
        if data.get("url"):
            img = await client.get(data["url"])
            return img.content
        raise ImageBackendError("TF image service returned no image")


# ---------------- intent detection (roadmap 2.2 static routing) ----------------

_INTENT_PATTERNS = re.compile(
    r"(draw|paint|sketch|illustrat|generate\s+(an?\s+)?(image|picture|photo|art)|"
    r"create\s+(an?\s+)?(image|picture|photo|art|logo|poster)|"
    r"text-to-image|image\s+of|picture\s+of|画|繪畫|生成(一张|一幅|个)?(图|图片|照片)|"
    r"帮我画|画一|来一?张)",
    re.IGNORECASE,
)


def detect_image_intent(text: str) -> bool:
    return bool(_INTENT_PATTERNS.search(text or ""))


REFINE_SYSTEM_PROMPT = (
    "You are an art director for a text-to-image model. Rewrite the user's request "
    "as ONE concise, vivid English image prompt (max 60 words). Describe subject, "
    "style, lighting and composition. Output only the prompt — no explanations, no quotes."
)
