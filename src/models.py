"""Pydantic schemas for the brainstorm app."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """LLM model configuration."""
    name: str
    model_id: str
    base_url: str
    api_key_env: str = ""
    api_key_value: str = ""
    temperature: float = 0.8
    max_tokens: int = 2048
    extra_body: Optional[dict] = None


class PositionAssignment(BaseModel):
    """Maps a debate position to a model."""
    position: str           # "S1", "S2", "O1", "O2"
    model_name: str         # "claude", "gemini", "qwen", "minimax"


class RoundResponse(BaseModel):
    """A single model's response in a round."""
    position: str
    model_name: str
    phase: str              # "r1", "r2_attack", "r2_defense", "r3_attack", "r3_defense", "summary", "synthesis"
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class UserNote(BaseModel):
    """User-injected input between rounds."""
    stage: int
    after_phase: str        # which phase this note follows
    text: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SessionState(BaseModel):
    """Full brainstorm session state — single source of truth."""
    session_id: str
    title: str
    idea: str
    background: str = ""    # additional context (pasted text, file contents, prior session synthesis)
    instructions: str = ""  # persistent instructions injected into every system prompt
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "new"     # state machine value
    stage: int = 1
    current_round: int = 0  # 0=not started, 1=r1 done, 2=first attack/defense done, etc.
    positions: list[PositionAssignment] = Field(default_factory=list)
    responses: list[RoundResponse] = Field(default_factory=list)
    summaries: dict[str, str] = Field(default_factory=dict)  # {"r1": "...", "r2": "..."}
    user_notes: list[UserNote] = Field(default_factory=list)
