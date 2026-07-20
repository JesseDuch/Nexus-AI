"""Platform configuration — all values overridable via environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Zhipu GLM upstream ---
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_default_model: str = "glm-4-flash"

    # --- Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # --- Database ---
    # Postgres-ready: set DATABASE_URL=postgresql+psycopg2://user:pass@host/db
    database_url: str = "sqlite:///./data/nexusai.db"

    # --- Image generation (Phase 2) ---
    # "cogview" uses Zhipu CogView via GLM_API_KEY; "tf-local" calls TF_IMAGE_URL
    image_backend: str = "cogview"
    cogview_model: str = "cogview-3-flash"
    tf_image_url: str = ""

    # --- Video generation (Phase 4) ---
    # "cogvideo" uses Zhipu CogVideoX via GLM_API_KEY; "tf-local" calls TF_VIDEO_URL
    video_backend: str = "cogvideo"
    cogvideo_model: str = "cogvideox-flash"
    tf_video_url: str = ""

    media_dir: str = "./data/media"

    # --- Code sandbox (Phase 5) ---
    # "subprocess" = rlimits-locked child process; "docker" = ephemeral containers
    sandbox_backend: str = "subprocess"
    sandbox_max_seconds: int = 30
    sandbox_max_memory_mb: int = 512
    sandbox_auto_install: bool = True
    sandbox_venv_dir: str = "./data/sandbox-venv"
    sandbox_docker_image: str = "python:3.12-slim"
    sandbox_max_attempts: int = 3

    # --- Intelligent orchestration (Phase 3) ---
    # Drop a trained TF-Agents policy artifact here (JSON linear policy or TF SavedModel dir)
    tf_agent_enabled: bool = True
    tf_agent_policy_path: str = "./data/policies/router_policy.json"
    self_reflect_ratio: float = 0.10   # 10% self-reflect quota (roadmap 3.1)

    # Shared secret protecting /internal/* service routes (defaults to jwt_secret)
    internal_token: str = ""

    # --- Quotas (Phase 7) ---
    daily_token_quota: int = 200_000      # per user
    daily_media_quota: int = 50           # images+videos per user
    daily_code_exec_quota: int = 100      # sandbox runs per user

    # --- Platform ---
    platform_name: str = "NexusAI"
    rate_limit_per_minute: int = 60
    frontend_dist: str = "../frontend/dist"

    def effective_internal_token(self) -> str:
        return self.internal_token or self.jwt_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
