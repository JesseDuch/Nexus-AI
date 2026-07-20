"""Pydantic schemas — OpenAI-compatible chat schema + console API schemas."""
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


# ---------------- OpenAI-compatible ----------------

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = ""
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """Matches the OpenAI /v1/chat/completions request body.
    Extra extension fields (tools=["code"], enable_image, ...) are accepted
    and ignored gracefully for forward compatibility with later phases.
    """
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    max_tokens: int | None = Field(default=None, gt=0)
    stop: str | list[str] | None = None
    tools: list[Any] | None = None          # roadmap extension: ["code"]
    enable_image: bool | None = None        # phase-2: force image generation
    enable_video: bool | None = None        # phase-4: force video generation
    enable_code_execution: bool | None = None  # phase-5: generate & run code in sandbox
    agent_mode: str | None = None           # phase-3 extension (accepted, no-op)

    model_config = {"extra": "allow"}


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# ---------------- Auth ----------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    is_admin: bool
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---------------- API keys ----------------

class ApiKeyCreate(BaseModel):
    name: str = Field(default="Default key", max_length=120)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    revoked: bool
    created_at: str
    last_used_at: str | None


class ApiKeyCreated(ApiKeyOut):
    key: str  # full secret, returned exactly once


# ---------------- Conversations ----------------

class ConsoleChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1)
    model: str | None = None
    stream: bool = True
    enable_image: bool | None = None   # Phase 2: force image generation
    enable_video: bool | None = None   # Phase 4: force video generation
    enable_code_execution: bool | None = None  # Phase 5: generate & run code


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationOut(BaseModel):
    id: int
    title: str
    model: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# ---------------- Usage ----------------

class UsageSummary(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    request_count: int
    image_count: int = 0
    video_count: int = 0
    code_exec_count: int = 0
    routing: dict[str, int] = {}   # Phase 3: action -> routed request count
    daily: list[dict[str, Any]]


# ---------------- Media ----------------

class MediaOut(BaseModel):
    id: int
    kind: str
    prompt: str
    url: str
    created_at: str


# ---------------- Images (OpenAI-compatible) ----------------

class ImageGenerationRequest(BaseModel):
    """OpenAI-compatible /v1/images/generations request body."""
    prompt: str = Field(min_length=1, max_length=2000)
    model: str | None = None
    n: int | None = Field(default=1, ge=1, le=4)
    size: str | None = "1024x1024"
    response_format: str | None = "url"

    model_config = {"extra": "allow"}
