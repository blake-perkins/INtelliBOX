"""Shared types for the AI module."""

from dataclasses import dataclass


@dataclass
class APIResponse:
    """Wraps OpenAI API response content with usage metadata."""

    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    retry_count: int = 0
    status: str = "success"
    error_message: str = ""
