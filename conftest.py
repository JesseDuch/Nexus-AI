"""Shared fixtures: isolated app with mocked GLM upstream, shared clean DB."""
import os
import shutil
import sys
from pathlib import Path

import pytest

# Isolate the app environment BEFORE importing it.
_TMP = Path(__file__).parent / ".tmp"
if _TMP.exists():
    shutil.rmtree(_TMP)
_TMP.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["MEDIA_DIR"] = str(_TMP / "media")
os.environ["SANDBOX_VENV_DIR"] = str(_TMP / "venv")
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-32b!!"
os.environ["GLM_API_KEY"] = "test-glm-key"
os.environ["SANDBOX_AUTO_INSTALL"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    # First registered user in the fresh test DB => platform admin.
    r = client.post("/api/auth/register", json={"email": "t@t.dev", "password": "secret123", "name": "T"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def api_key(client, auth_headers):
    r = client.post("/api/keys", json={"name": "test"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["key"]


@pytest.fixture(autouse=True)
def mock_glm(monkeypatch):
    """Mock the GLM upstream so tests never hit the network."""
    from app import glm

    async def fake_chat(payload):
        system = payload["messages"][0].get("content", "")
        prompt = payload["messages"][-1]["content"]
        # The code-generation step gets a real runnable program back.
        if "Code Runner" in system:
            content = "```python\nprint(sum(i*i for i in range(1, 6)))\n```"
        elif "art director" in system.lower() or "director" in system.lower():
            content = "a vivid test image prompt"
        else:
            content = f"MOCKED: {prompt[:40]}"
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1,
            "model": payload["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

    async def fake_stream(payload):
        for tok in ["MOCK", "ED", " reply"]:
            yield 'data: {"choices":[{"delta":{"content":"' + tok + '"}}]}'
        yield "data: [DONE]"

    monkeypatch.setattr(glm, "chat_completion", fake_chat)
    monkeypatch.setattr(glm, "chat_completion_stream", fake_stream)
    yield
