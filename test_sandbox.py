"""Sandbox service unit tests (roadmap 8.1)."""
import pytest

from app import sandbox_service

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _sandbox_env(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox_service.settings, "sandbox_auto_install", False)
    monkeypatch.setattr(sandbox_service.settings, "media_dir", str(tmp_path / "media"))


@pytest.mark.asyncio
async def test_python_execution():
    r = await sandbox_service.execute_code("print(6*7)", "python")
    assert r["success"]
    assert "42" in r["stdout"]
    assert r["exit_code"] == 0


@pytest.mark.asyncio
async def test_syntax_error_reported():
    r = await sandbox_service.execute_code("def broken(:\n    pass", "python")
    assert not r["success"]
    assert r["stderr"]


@pytest.mark.asyncio
async def test_timeout_enforced():
    r = await sandbox_service.execute_code("import time\ntime.sleep(60)", "python", timeout_seconds=2)
    assert not r["success"]
    assert "timed out" in r["stderr"].lower()


@pytest.mark.asyncio
async def test_network_blocked():
    code = (
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=3)\n"
        "    print('NET_OPEN')\n"
        "except Exception as e:\n"
        "    print('blocked:', type(e).__name__)\n"
    )
    r = await sandbox_service.execute_code(code, "python", timeout_seconds=15)
    assert "NET_OPEN" not in r["stdout"]
    assert "blocked" in r["stdout"]


@pytest.mark.asyncio
async def test_unsupported_language():
    r = await sandbox_service.execute_code("echo hi", "bash")
    assert not r["success"]
    assert "Unsupported" in r["stderr"]
