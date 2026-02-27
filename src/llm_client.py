"""Unified OpenAI-compatible async LLM client for all brainstorm models."""

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import openai
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root, then optionally a second file (ENV_FILE)
_project_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_project_env)  # Load project .env first
_extra_env = os.getenv("ENV_FILE")
if _extra_env and Path(_extra_env).exists():
    load_dotenv(_extra_env)  # Then overlay with extra env file (e.g. shared API keys)


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    error: Optional[str] = None


# Model registry — all use OpenAI-compatible endpoints
# Each model can be overridden via environment variables:
#   {NAME}_MODEL_ID, {NAME}_BASE_URL, {NAME}_API_KEY, {NAME}_MAX_TOKENS
#
# Global fallbacks (for single-provider setups like OpenRouter / Copilot):
#   BRAINSTORM_BASE_URL — used when {NAME}_BASE_URL is not set
#   BRAINSTORM_API_KEY  — used when {NAME}_API_KEY is not set
_global_base_url = os.getenv("BRAINSTORM_BASE_URL", "")
_global_api_key = os.getenv("BRAINSTORM_API_KEY", "")


def _model_config(name: str, default_model_id: str, default_base_url: str,
                  default_api_key_env: str, default_max_tokens: int = 16384,
                  extra_kwargs: dict = None) -> dict:
    prefix = name.upper()
    config = {
        "model_id": os.getenv(f"{prefix}_MODEL_ID", default_model_id),
        "base_url": os.getenv(f"{prefix}_BASE_URL", _global_base_url or default_base_url),
        "api_key": os.getenv(f"{prefix}_API_KEY",
                             _global_api_key or os.getenv(default_api_key_env, "")),
        "max_tokens": int(os.getenv(f"{prefix}_MAX_TOKENS", str(default_max_tokens))),
    }
    if extra_kwargs:
        config["extra_kwargs"] = extra_kwargs
    return config


MODELS = {
    "claude": _model_config(
        "claude",
        default_model_id="claude-sonnet-4-6",
        default_base_url="https://api.anthropic.com/v1/",
        default_api_key_env="ANTHROPIC_API_KEY",
    ),
    "gemini": _model_config(
        "gemini",
        default_model_id="gemini-3.1-pro-preview",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_api_key_env="GOOGLE_API_KEY",
        extra_kwargs={"max_completion_tokens": 16384},
    ),
    "qwen": _model_config(
        "qwen",
        default_model_id="qwen3.5-plus",
        default_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        default_api_key_env="DASHSCOPE_API_KEY",
    ),
    "minimax": _model_config(
        "minimax",
        default_model_id="MiniMax-M2.5",
        default_base_url="https://api.minimax.io/v1",
        default_api_key_env="MINIMAX_API_KEY",
    ),
}

# Per-provider semaphores for rate limiting
_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_semaphore(name: str) -> asyncio.Semaphore:
    if name not in _semaphores:
        _semaphores[name] = asyncio.Semaphore(3)
    return _semaphores[name]


async def call_model(model_name: str, system: str, user: str) -> LLMResponse:
    """Call a model using its OpenAI-compatible endpoint."""
    config = MODELS[model_name]
    sem = _get_semaphore(model_name)

    async with sem:
        t0 = time.monotonic()
        try:
            client = openai.AsyncOpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"],
                max_retries=2,
                timeout=600.0,
            )

            kwargs = {
                "model": config["model_id"],
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.8,
            }

            # Gemini needs max_completion_tokens instead of max_tokens
            if "extra_kwargs" in config:
                kwargs.update(config["extra_kwargs"])
            else:
                kwargs["max_tokens"] = config["max_tokens"]

            resp = await client.chat.completions.create(**kwargs)

            text = resp.choices[0].message.content or ""
            # Strip <think>...</think> tags (MiniMax M2.5 thinking mode leaks these)
            text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
            usage = resp.usage
            latency = (time.monotonic() - t0) * 1000

            return LLMResponse(
                text=text,
                model=config["model_id"],
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            return LLMResponse(
                text="",
                model=config["model_id"],
                tokens_in=0,
                tokens_out=0,
                latency_ms=latency,
                error=str(e),
            )
