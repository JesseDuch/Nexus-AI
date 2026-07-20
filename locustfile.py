"""Locust load test (roadmap 8.2) — simulates concurrent developers.

Run:
  locust -f locustfile.py --host http://localhost:8000 \
      --users 50 --spawn-rate 5 --run-time 2m --headless

Set NEXUSAI_API_KEY to a real sk-nx- key before running.
"""
import os

from locust import HttpUser, between, task


class DeveloperUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.key = os.environ.get("NEXUSAI_API_KEY", "")
        self.headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}

    @task(5)
    def chat_unary(self):
        self.client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Say hello in one word"}]},
            headers=self.headers,
            name="/v1/chat/completions",
        )

    @task(2)
    def chat_stream(self):
        self.client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Count to 5"}], "stream": True},
            headers=self.headers,
            name="/v1/chat/completions (stream)",
        )

    @task(1)
    def models(self):
        self.client.get("/v1/models", headers=self.headers, name="/v1/models")

    @task(1)
    def health(self):
        self.client.get("/api/health", name="/api/health")
