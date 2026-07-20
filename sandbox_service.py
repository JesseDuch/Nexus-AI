"""Isolated code execution service (roadmap 5.1).

Two backends, same interface:
  • "subprocess" — locked-down child process: CPU/memory/file rlimits, wall-clock
    timeout, blocked network (non-routable proxy + scrubbed env), fresh temp
    HOME/cwd. Safe for a trusted single-tenant deployment; use the Docker backend
    for hostile multi-tenant code.
  • "docker" — spawns an ephemeral container per run (SANDBOX_DOCKER_IMAGE) with
    --network none, --memory/--cpus limits, read-only rootfs. Requires the Docker
    socket in the container (mount /var/run/docker.sock at deploy time).

Python code runs directly; common scientific packages (numpy, matplotlib, …) are
auto-installed on demand into an isolated venv directory. matplotlib plots saved
next to the script are captured and returned as /media PNG URLs — and can be
stitched into videos by the Phase-4 pipeline.
"""
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .config import get_settings

settings = get_settings()

MAX_OUTPUT_CHARS = 6000
COMMON_PACKAGES = ("numpy", "matplotlib", "pandas", "pillow", "requests", "scipy")


class SandboxError(Exception):
    pass


def _limits():
    """Apply rlimits inside the child process (POSIX only)."""
    cpu = settings.sandbox_max_seconds
    mem = settings.sandbox_max_memory_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))  # 20MB files
        # BLAS/numpy worker threads need headroom; fork-bombs stay capped.
        resource.setrlimit(resource.RLIMIT_NPROC, (512, 512))
    except (ValueError, OSError):
        pass  # platform doesn't support a limit — continue anyway


def _scrubbed_env(workdir: str) -> dict:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "MPLBACKEND": "Agg",
        # Keep native BLAS pools small so they fit the sandbox rlimits.
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        # Block network egress via proxy blackhole; scrub inherited credentials.
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "http_proxy": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "no_proxy": "",
    }


def _venv_dir() -> Path:
    return Path(settings.sandbox_venv_dir).expanduser().resolve()


def _venv_python() -> str | None:
    venv_py = _venv_dir() / "bin" / "python"
    return str(venv_py) if venv_py.exists() else None


import threading

_venv_lock = threading.Lock()


def _ensure_packages(code: str) -> None:
    """Best-effort install of common packages the generated code imports.
    Serialised per-process: concurrent runs must not create/install the venv twice."""
    if not settings.sandbox_auto_install:
        return
    imports = set(re.findall(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", code, re.MULTILINE))
    wanted = {p.lower() for p in imports if p.lower() in COMMON_PACKAGES or p.lower() == "pil"}
    if not wanted:
        return
    pkgs = sorted({"pillow" if p == "pil" else p for p in wanted})
    venv_dir = _venv_dir()
    with _venv_lock:
        try:
            if _venv_python() is None:
                venv_dir.parent.mkdir(parents=True, exist_ok=True)
                # --system-site-packages: inherit host scientific stack (numpy,
                # matplotlib…) — PyPI may be unreachable from the sandbox host.
                subprocess.run(
                    [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
                    check=True, capture_output=True, timeout=180,
                )
            probe = subprocess.run(
                [_venv_python(), "-c", "import " + ", ".join(pkgs)],
                capture_output=True, timeout=30,
            )
            if probe.returncode != 0:
                subprocess.run(
                    [_venv_python(), "-m", "pip", "install", "-q", "--disable-pip-version-check", *pkgs],
                    capture_output=True, timeout=300,
                )
        except (subprocess.SubprocessError, OSError):
            pass  # the run itself will surface any still-missing module


async def execute_code(
    code: str,
    language: str = "python",
    timeout_seconds: int | None = None,
) -> dict:
    """Run code in the sandbox. Returns {success, stdout, stderr, exit_code,
    duration_ms, output_files:[{filename,url}], backend}."""
    import asyncio

    if settings.sandbox_backend == "docker":
        return await asyncio.to_thread(_execute_docker, code, language, timeout_seconds)
    return await asyncio.to_thread(_execute_subprocess, code, language, timeout_seconds)


# ---------------- subprocess backend ----------------

def _execute_subprocess(code: str, language: str, timeout_seconds: int | None) -> dict:
    language = language.lower()
    if language not in ("python", "py", "javascript", "js", "node"):
        return _result(False, "", f"Unsupported language: {language} (python/javascript)", -1, 0)

    if language in ("python", "py"):
        _ensure_packages(code)

    timeout = min(timeout_seconds or settings.sandbox_max_seconds, settings.sandbox_max_seconds)
    workdir = tempfile.mkdtemp(prefix="nexus_sandbox_")
    media_out = Path(settings.media_dir).expanduser().resolve()
    media_out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    try:
        if language in ("python", "py"):
            script = Path(workdir) / "main.py"
            script.write_text(code)
            interpreter = _venv_python() or sys.executable
            cmd = [interpreter, str(script)]
        else:
            if shutil.which("node") is None:
                return _result(False, "", "Node.js is not installed in this environment", -1, 0)
            script = Path(workdir) / "main.js"
            script.write_text(code)
            cmd = ["node", str(script)]

        try:
            proc = subprocess.run(
                cmd,
                cwd=workdir,
                env=_scrubbed_env(workdir),
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=_limits if hasattr(os, "fork") else None,
            )
            stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = f"Execution timed out after {timeout}s"
            exit_code = -9

        duration_ms = int((time.monotonic() - started) * 1000)

        # Capture generated images (plots, animation frames) into the media store.
        output_files = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif"):
            for f in sorted(Path(workdir).glob(ext)):
                dest = f"img_{uuid.uuid4().hex[:16]}{f.suffix}"
                (media_out / dest).write_bytes(f.read_bytes())
                output_files.append({"filename": f.name, "url": f"/media/{dest}"})

        return {
            "success": exit_code == 0,
            "stdout": stdout[-MAX_OUTPUT_CHARS:],
            "stderr": stderr[-MAX_OUTPUT_CHARS:],
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "output_files": output_files,
            "backend": "subprocess",
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------- docker backend (production) ----------------

def _execute_docker(code: str, language: str, timeout_seconds: int | None) -> dict:
    if shutil.which("docker") is None:
        return _result(False, "", "Docker backend selected but the docker CLI is unavailable", -1, 0)
    image = settings.sandbox_docker_image
    timeout = min(timeout_seconds or settings.sandbox_max_seconds, settings.sandbox_max_seconds)
    lang = language.lower()
    if lang in ("python", "py"):
        inner = ["python", "-c", code]
    elif lang in ("javascript", "js", "node"):
        inner = ["node", "-e", code]
    else:
        return _result(False, "", f"Unsupported language: {language}", -1, 0)
    started = time.monotonic()
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", f"{settings.sandbox_max_memory_mb}m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        image, *inner,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, exit_code = "", f"Execution timed out after {timeout}s", -9
    duration_ms = int((time.monotonic() - started) * 1000)
    return {
        "success": exit_code == 0,
        "stdout": stdout[-MAX_OUTPUT_CHARS:],
        "stderr": stderr[-MAX_OUTPUT_CHARS:],
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "output_files": [],
        "backend": "docker",
    }


def _result(success: bool, stdout: str, stderr: str, exit_code: int, duration_ms: int) -> dict:
    return {
        "success": success,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "output_files": [],
        "backend": settings.sandbox_backend,
    }


# ---------------- formatting for chat ----------------

def format_result_markdown(result: dict, language: str) -> str:
    lang_label = "Python" if language.lower() in ("python", "py") else "JavaScript"
    parts = []
    if result["stdout"].strip():
        parts.append(f"**Output**\n```\n{result['stdout'].strip()}\n```")
    if result["stderr"].strip():
        parts.append(f"**Errors**\n```\n{result['stderr'].strip()}\n```")
    for f in result["output_files"]:
        parts.append(f"![{f['filename']}]({f['url']})")
    if not parts:
        parts.append(
            f"_{lang_label} ran successfully with no output._"
            if result["success"]
            else f"_{lang_label} exited with code {result['exit_code']} and no output._"
        )
    badge = "✅" if result["success"] else "❌"
    header = f"{badge} **Sandbox** · {lang_label} · exit {result['exit_code']} · {result['duration_ms']}ms\n\n"
    return header + "\n\n".join(parts)
