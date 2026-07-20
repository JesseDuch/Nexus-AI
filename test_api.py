"""End-to-end API tests (roadmap 8.1) — all public endpoints, including error cases."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "image_backend" in body and "video_backend" in body and "sandbox_backend" in body


def test_register_and_login(client):
    r = client.post("/api/auth/register", json={"email": "u2@t.dev", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["token"]
    r2 = client.post("/api/auth/login", json={"email": "u2@t.dev", "password": "secret123"})
    assert r2.status_code == 200


def test_register_duplicate_email_conflict(client):
    r = client.post("/api/auth/register", json={"email": "u2@t.dev", "password": "secret123"})
    assert r.status_code == 409


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "u2@t.dev", "password": "wrong"})
    assert r.status_code == 401


def test_profile_requires_auth(client):
    assert client.get("/api/user/profile").status_code in (401, 403)


def test_api_key_lifecycle(client, auth_headers):
    # create
    r = client.post("/api/keys", json={"name": "k1"}, headers=auth_headers)
    assert r.status_code == 201
    key = r.json()
    assert key["key"].startswith("sk-nx-")
    # list
    keys = client.get("/api/keys", headers=auth_headers).json()
    assert any(k["id"] == key["id"] for k in keys)
    # revoke
    assert client.delete(f"/api/keys/{key['id']}", headers=auth_headers).status_code == 204
    # revoked key rejected on /v1
    r2 = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]},
                     headers={"Authorization": f"Bearer {key['key']}"})
    assert r2.status_code == 401


def test_chat_completions_unary(client, api_key):
    r = client.post("/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "hello"}]},
                    headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"].startswith("MOCKED:")
    assert body["usage"]["total_tokens"] == 10
    assert body["routing"]["action"] == "chat"


def test_chat_completions_stream(client, api_key):
    with client.stream("POST", "/v1/chat/completions",
                       json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
                       headers={"Authorization": f"Bearer {api_key}"}) as r:
        assert r.status_code == 200
        text = "".join(r.iter_text())
    assert "data:" in text and "[DONE]" in text


def test_chat_requires_api_key(client):
    r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code in (401, 403)


def test_chat_empty_messages_rejected(client, api_key):
    r = client.post("/v1/chat/completions", json={"messages": []},
                    headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 400


def test_models_list(client, api_key):
    r = client.get("/v1/models", headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["data"]]
    assert "nexus-chat" in ids


def test_agents_list(client, api_key):
    r = client.get("/v1/agents", headers={"Authorization": f"Bearer {api_key}"})
    assert r.status_code == 200
    actions = [a["id"] for a in r.json()["data"]]
    for a in ("chat", "code_exec", "image_gen", "video_gen"):
        assert a in actions
    assert r.json()["routing"]["policy"] in ("rules-v1", "tf-agents")


def test_console_chat_and_history(client, auth_headers):
    r = client.post("/api/chat", json={"message": "hello there", "stream": False}, headers=auth_headers)
    assert r.status_code == 200
    conv_id = r.json()["conversation_id"]
    convs = client.get("/api/conversations", headers=auth_headers).json()
    assert any(c["id"] == conv_id for c in convs)
    detail = client.get(f"/api/conversations/{conv_id}", headers=auth_headers).json()
    assert len(detail["messages"]) >= 2


def test_console_chat_stream_includes_routing(client, auth_headers):
    with client.stream("POST", "/api/chat", json={"message": "compute 5 factorial and run it", "enable_code_execution": False},
                       headers=auth_headers) as r:
        text = "".join(r.iter_text())
    assert '"routing"' in text


def test_usage_summary(client, auth_headers):
    r = client.get("/api/user/usage", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total_tokens" in body and "daily" in body and "routing" in body
    assert len(body["daily"]) == 14


def test_feedback(client, auth_headers):
    r = client.post("/api/feedback", json={"rating": 1}, headers=auth_headers)
    assert r.status_code == 201


def test_metrics(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert "uptime_seconds" in r.json()


def test_admin_forbidden_for_non_admin(client, auth_headers):
    # auth_headers user is the FIRST registered user in this test DB => admin.
    # register a second (non-admin) user and confirm denial.
    r = client.post("/api/auth/register", json={"email": "second@t.dev", "password": "secret123"})
    token = r.json()["token"]
    r2 = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 403


def test_admin_stats_for_admin(client, auth_headers):
    # Promote the fixture user to admin deterministically (test order independent).
    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as s:
        u = s.query(User).filter(User.email == "t@t.dev").first()
        u.is_admin = True
        s.commit()
    r = client.get("/api/admin/stats", headers=auth_headers)
    assert r.status_code == 200
    assert "users" in r.json()


def test_internal_routes_require_token(client):
    r = client.post("/internal/code_sandbox", json={"code": "print(1)"})
    assert r.status_code == 403


def test_internal_sandbox_runs_code(client):
    import os
    secret = os.environ["JWT_SECRET"]
    r = client.post("/internal/code_sandbox", json={"code": "print(6*7)"},
                    headers={"X-Internal-Token": secret})
    assert r.status_code == 200
    assert "42" in r.json()["stdout"]


def test_routing_natural_language(client, api_key):
    cases = {
        "draw a castle in the sky": "image_gen",
        "generate a video of a rocket launch": "video_gen",
        "compute the sum of 1..100 and run the code": "code_exec",
    }
    for msg, expected in cases.items():
        r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": msg}]},
                        headers={"Authorization": f"Bearer {api_key}"})
        assert r.status_code == 200
        assert r.json()["routing"]["action"] == expected, msg
