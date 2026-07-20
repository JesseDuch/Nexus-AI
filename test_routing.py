"""Unit tests for the orchestration core (roadmap 8.1)."""
from app import agent_service


def _decide(text, explicit=None):
    return agent_service.choose_action(
        user_text=text,
        conversation_len=2,
        quota_remaining=1000,
        user_total_requests=5,
        explicit=explicit or {},
    )


def test_explicit_flags_win():
    assert _decide("hello", {"code": True})["action"] == "code_exec"
    assert _decide("hello", {"video": True})["action"] == "video_gen"
    assert _decide("hello", {"image": True})["action"] == "image_gen"


def test_natural_language_intents():
    assert _decide("generate a video of a cat")["action"] == "video_gen"
    assert _decide("draw a sunset over the ocean")["action"] == "image_gen"
    assert _decide("compute 10! and run it")["action"] == "code_exec"
    assert _decide("what is the capital of France?")["action"] == "chat"


def test_decision_shape():
    d = _decide("hello")
    assert set(d) >= {"action", "policy", "reason", "self_reflect"}
    assert d["policy"] == "rules-v1"
    assert isinstance(d["self_reflect"], bool)


def test_reward_shaping():
    good = agent_service.compute_reward(success=True, latency_ms=1000)
    bad = agent_service.compute_reward(success=False, latency_ms=1000)
    assert good > bad
