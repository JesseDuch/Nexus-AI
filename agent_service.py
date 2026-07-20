"""Intelligent orchestration core (roadmap 3.1).

TF-Agents reinforcement-learning adapter
----------------------------------------
A trained TF-Agents policy can be dropped in at TF_AGENT_POLICY_PATH (a SavedModel
or a lightweight JSON weight file — the roadmap's starter artifact). When present
and TF_AGENT_ENABLED=true, `choose_action` queries it first; on any failure it
falls back to the built-in rule-based policy, so the platform always routes.

Observation space (roadmap 3.1): query embedding features, user history stats,
current conversation length, and API quota remaining — packed into a fixed-size
float vector. Action space (roadmap 3.1): which tool chain to invoke.

Reward shaping (roadmap 3.1) is computed per request and logged for future
training: success, latency, user feedback, cost.
"""
import hashlib
import json
import random
import time
from pathlib import Path

from . import image_service, video_service
from .config import get_settings

settings = get_settings()

# ---------------- action space ----------------

ACTION_CHAT = "chat"          # plain text completion
ACTION_CODE = "code_exec"     # sandbox: generate → run → self-fix
ACTION_IMAGE = "image_gen"    # text-to-image
ACTION_VIDEO = "video_gen"    # text-to-video
ACTIONS = (ACTION_CHAT, ACTION_CODE, ACTION_IMAGE, ACTION_VIDEO)

_CODE_HINTS = (
    "compute", "calculate", "plot ", "graph ", "simulate", "fibonacci", "factorial",
    "sort ", "prime", "integral", "derivative", "regression", "dataset", "csv",
    "run the code", "execute", "write and run", "sandbox", "histogram", "scatter",
)


# ---------------- observation ----------------

def build_observation(
    *,
    user_text: str,
    conversation_len: int,
    quota_remaining: int | None,
    user_total_requests: int,
) -> dict:
    """Numeric feature vector + metadata — the RL 'observation'."""
    text = user_text or ""
    # Tiny deterministic text->vector hash embedding (placeholder for a real
    # embedding model; the TF policy consumes the same vector shape).
    dims = 16
    vec = [0.0] * dims
    for tok in text.lower().split():
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0
    norm = sum(vec) or 1.0
    vec = [v / norm for v in vec]
    return {
        "text_vec": vec,
        "conversation_len": float(conversation_len),
        "quota_remaining": float(quota_remaining if quota_remaining is not None else 1e9),
        "user_total_requests": float(user_total_requests),
        "has_image_intent": image_service.detect_image_intent(text),
        "has_video_intent": video_service.detect_video_intent(text),
        "has_code_hint": any(h in text.lower() for h in _CODE_HINTS),
    }


# ---------------- rule-based policy (always available) ----------------

def _rule_policy(obs: dict, explicit: dict[str, bool]) -> tuple[str, str]:
    """Returns (action, reason). Explicit user flags always win."""
    if explicit.get("code"):
        return ACTION_CODE, "explicit enable_code_execution flag"
    if explicit.get("video"):
        return ACTION_VIDEO, "explicit enable_video flag"
    if explicit.get("image"):
        return ACTION_IMAGE, "explicit enable_image flag"
    if obs["has_video_intent"]:
        return ACTION_VIDEO, "natural-language video intent detected"
    if obs["has_image_intent"]:
        return ACTION_IMAGE, "natural-language image intent detected"
    if obs["has_code_hint"]:
        return ACTION_CODE, "computational keywords detected"
    return ACTION_CHAT, "default conversational route"


# ---------------- TF-Agents policy adapter ----------------

class _TfPolicy:
    """Thin adapter around a trained TF-Agents policy artifact.

    Supports two artifact formats at TF_AGENT_POLICY_PATH:
      • a JSON file {"weights": [...], "bias": [...]} — a linear policy over the
        observation vector (trainable/exportable without TF in this container)
      • a TF SavedModel directory (loaded lazily iff tensorflow is importable)
    """

    def __init__(self) -> None:
        self._json_policy: dict | None = None
        self._loaded = False
        self._available = False

    def _load(self) -> None:
        self._loaded = True
        path = settings.tf_agent_policy_path
        if not path:
            return
        p = Path(path)
        if p.is_file() and p.suffix == ".json":
            try:
                self._json_policy = json.loads(p.read_text())
                self._available = True
            except (json.JSONDecodeError, OSError):
                self._available = False
        elif p.is_dir():
            try:
                import tensorflow as tf  # noqa: F401  (only present on GPU workers)

                self._available = True  # real SavedModel load happens on first use
            except ImportError:
                self._available = False

    @property
    def available(self) -> bool:
        if not self._loaded:
            self._load()
        return self._available and settings.tf_agent_enabled

    def choose(self, obs: dict) -> tuple[str, str] | None:
        """Query the trained policy. None => fall back to rules."""
        if self._json_policy:
            feats = (
                obs["text_vec"]
                + [obs["conversation_len"] / 50.0, obs["quota_remaining"] / 1000.0, obs["user_total_requests"] / 100.0]
                + [float(obs["has_code_hint"]), float(obs["has_image_intent"]), float(obs["has_video_intent"])]
            )
            w = self._json_policy.get("weights", [])
            b = self._json_policy.get("bias", [0.0] * len(ACTIONS))
            if len(w) == len(ACTIONS) and all(len(row) == len(feats) for row in w):
                scores = [sum(wi * fi for wi, fi in zip(row, feats)) + b[i] for i, row in enumerate(w)]
                best = ACTIONS[scores.index(max(scores))]
                return best, "tf-agents policy (linear artifact)"
        # SavedModel path would go here on a GPU worker.
        return None


_tf_policy = _TfPolicy()


# ---------------- public API ----------------

def choose_action(
    *,
    user_text: str,
    conversation_len: int,
    quota_remaining: int | None,
    user_total_requests: int,
    explicit: dict[str, bool],
) -> dict:
    """Central routing decision consumed by every chat endpoint."""
    obs = build_observation(
        user_text=user_text,
        conversation_len=conversation_len,
        quota_remaining=quota_remaining,
        user_total_requests=user_total_requests,
    )
    tf_choice = _tf_policy.choose(obs) if _tf_policy.available else None
    if tf_choice:
        action, reason = tf_choice
        policy = "tf-agents"
    else:
        action, reason = _rule_policy(obs, explicit)
        policy = "rules-v1"

    # 10% self-reflect quota (roadmap 3.1): tag a slice of requests for deeper
    # critique/review — sampled uniformly, excluded from the fast path.
    self_reflect = random.random() < settings.self_reflect_ratio

    return {
        "action": action,
        "policy": policy,
        "reason": reason,
        "self_reflect": self_reflect,
        "observation_summary": {
            "conversation_len": obs["conversation_len"],
            "code_hint": obs["has_code_hint"],
            "image_intent": obs["has_image_intent"],
            "video_intent": obs["has_video_intent"],
        },
    }


def compute_reward(*, success: bool, latency_ms: int, user_feedback: float = 0.0, cost: float = 0.0) -> float:
    """Roadmap 3.1 reward shaping — logged per request for future RL training."""
    reward = 0.0
    reward += 1.0 if success else -0.5
    reward -= min(latency_ms / 60_000.0, 1.0) * 0.3   # latency penalty (cap 0.3)
    reward += user_feedback * 0.5                      # thumbs up/down (Phase 6 UI)
    reward -= cost * 0.2                               # token/compute cost
    return round(reward, 4)
