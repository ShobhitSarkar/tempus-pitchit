"""Shared LLM client configuration for the copilot's two call sites.

Both the CRM scorer (extract_crm_signals.py) and the brief generator
(backend/services/generation.py) go through this module. It uses the OpenAI API
with structured (schema-constrained) output. Real calls happen when
OPENAI_API_KEY is available; callers fall back to a deterministic stub/template
otherwise so the app still runs with no key.

Provider specifics live here on purpose — swapping providers is a one-file change.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

# Cheap, structured-output-capable default. Override with LLM_MODEL (e.g. gpt-4o).
DEFAULT_MODEL = "gpt-4o-mini"
MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODEL)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Real calls are made when an API key is present. Force on/off with LLM_ENABLED.
LLM_ENABLED = _env_flag("LLM_ENABLED", default=bool(os.environ.get("OPENAI_API_KEY")))


@lru_cache(maxsize=1)
def get_client():
    """Return a lazily-constructed, cached OpenAI client.

    The SDK reads OPENAI_API_KEY from the environment and auto-retries transient
    errors with backoff.
    """
    from openai import OpenAI

    return OpenAI(max_retries=2, timeout=60.0)


T = TypeVar("T", bound=BaseModel)


def structured_complete(system: str, user: str, schema: type[T], max_tokens: int = 1024) -> T:
    """Run one chat completion constrained to `schema` and return the parsed model.

    Raises on a refusal or empty parse so callers can fall back gracefully.
    """
    completion = get_client().chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=schema,
        max_completion_tokens=max_tokens,
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        raise RuntimeError(f"model refused: {message.refusal}")
    if message.parsed is None:
        raise RuntimeError("model returned no structured output")
    return message.parsed
