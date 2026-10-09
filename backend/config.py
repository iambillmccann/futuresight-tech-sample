from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


@dataclass(frozen=True)
class Settings:
    serpapi_api_key: str
    openai_api_key: str
    openai_model: str
    cache_ttl_seconds: int
    cache_max_entries: int
    max_reviews: int
    provider_timeout_seconds: int
    model_context_chars: int
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        )
        return cls(
            serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            cache_ttl_seconds=_positive_int("CACHE_TTL_SECONDS", 24 * 60 * 60),
            cache_max_entries=_positive_int("CACHE_MAX_ENTRIES", 50),
            max_reviews=_positive_int("MAX_REVIEWS", 200),
            provider_timeout_seconds=_positive_int("PROVIDER_TIMEOUT_SECONDS", 20),
            model_context_chars=_positive_int("MODEL_CONTEXT_CHARS", 60_000),
            cors_origins=tuple(
                origin.strip() for origin in origins.split(",") if origin.strip()
            ),
        )
