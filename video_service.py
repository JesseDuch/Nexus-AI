"""Video generation service (roadmap 4.1) — pluggable backend.

Backends:
  • "cogvideo" — Zhipu CogVideoX via GLM_API_KEY (async task + polling, works now)
  • "tf-local" — your own TensorFlow text-to-video diffusion HTTP service
                 (set TF_VIDEO_URL; accepts {"prompt"} and returns an MP4 binary
                 or {"url": ...})

Generated MP4s are stored locally and served from /media/{filename}.
Also implements the roadmap's second pipeline: code-animation-frame stitching via
FFmpeg (`stitch_frames`).
"""
import asyncio
import re
import subprocess
import uuid
from pathlib import Path

import httpx

from .config import get_settings

settings = get_settings()

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)


def media_dir() -> Path:
    d = Path(settings.media_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


class VideoBackendError(Exception):
    pass


# ---------------- public entry points ----------------

async def generate_video(prompt: str) -> tuple[str, str]:
    """Generate an MP4, persist it, return (filename, public_url_path)."""
    backend = settings.video_backend.lower()
    if backend == "tf-local":
        content = await _generate_tf_local(prompt)
    else:
        content = await _generate_cogvideo(prompt)
    return _save_mp4(content)


def stitch_frames(frames_dir: Path, fps: int = 12) -> tuple[str, str]:
    """Roadmap pipeline #1: compile a directory of animation frames into an MP4."""
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        raise VideoBackendError(f"No PNG frames found in {frames_dir}")
    filename = f"vid_{uuid.uuid4().hex[:16]}.mp4"
    out = media_dir() / filename
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps), "-i", str(frames_dir / "%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size < 1000:
        raise VideoBackendError(f"FFmpeg stitching failed: {proc.stderr[-300:]}")
    return filename, f"/media/{filename}"


def _save_mp4(content: bytes) -> tuple[str, str]:
    if len(content) < 1000:
        raise VideoBackendError("Video backend returned an invalid/empty file")
    filename = f"vid_{uuid.uuid4().hex[:16]}.mp4"
    (media_dir() / filename).write_bytes(content)
    return filename, f"/media/{filename}"


# ---------------- CogVideoX backend ----------------

async def _generate_cogvideo(prompt: str) -> bytes:
    base = settings.glm_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.glm_api_key}"}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # Submit the async generation task — retry through upstream overload.
        task_id = None
        last_err = ""
        for attempt in range(4):
            resp = await client.post(
                f"{base}/videos/generations",
                headers=headers,
                json={"model": settings.cogvideo_model, "prompt": prompt},
            )
            data = resp.json()
            if resp.status_code < 400 and data.get("id"):
                task_id = data["id"]
                break
            last_err = (data.get("error") or {}).get("message", resp.text[:200]) if isinstance(data, dict) else resp.text[:200]
            await asyncio.sleep(5 + attempt * 5)  # 5s, 10s, 15s backoff
        if not task_id:
            raise VideoBackendError(f"CogVideoX task submission failed: {last_err}")

        # Poll for the result (video gen typically takes 1–3 minutes).
        deadline = 600  # seconds
        waited = 0
        while waited < deadline:
            await asyncio.sleep(8)
            waited += 8
            poll = await client.get(f"{base}/async-result/{task_id}", headers=headers)
            pdata = poll.json()
            status = pdata.get("task_status", "")
            if status == "SUCCESS":
                results = pdata.get("video_result") or []
                url = results[0].get("url") if results else None
                if not url:
                    raise VideoBackendError("CogVideoX succeeded but returned no video URL")
                vid = await client.get(url)
                if vid.status_code >= 400:
                    raise VideoBackendError("Failed to download generated video")
                return vid.content
            if status in ("FAIL", "FAILED"):
                raise VideoBackendError(f"CogVideoX task failed: {str(pdata)[:200]}")
        raise VideoBackendError("CogVideoX task timed out after 10 minutes")


# ---------------- TF-local backend ----------------

async def _generate_tf_local(prompt: str) -> bytes:
    if not settings.tf_video_url:
        raise VideoBackendError("TF_VIDEO_URL is not configured for the tf-local backend")
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(settings.tf_video_url, json={"prompt": prompt})
        if resp.status_code >= 400:
            raise VideoBackendError(f"TF video service error ({resp.status_code}): {resp.text[:300]}")
        if resp.headers.get("content-type", "").startswith("video/"):
            return resp.content
        data = resp.json()
        if data.get("url"):
            vid = await client.get(data["url"])
            return vid.content
        raise VideoBackendError("TF video service returned no video")


# ---------------- intent detection ----------------

_INTENT_PATTERNS = re.compile(
    r"(generate\s+(a\s+)?video|create\s+(a\s+)?video|make\s+(a\s+)?video|"
    r"text-to-video|video\s+of|animate\s+|animation\s+of|"
    r"生成(一段|一个)?视频|制作视频|来一?段视频|动画)",
    re.IGNORECASE,
)


def detect_video_intent(text: str) -> bool:
    return bool(_INTENT_PATTERNS.search(text or ""))


REFINE_VIDEO_PROMPT = (
    "You are a director for a text-to-video model. Rewrite the user's request as ONE "
    "concise, vivid English video prompt (max 60 words). Describe the subject, motion, "
    "camera movement, style and lighting. Output only the prompt — no explanations, no quotes."
)
