"""Shared Anthropic client configuration for the copilot's two LLM call sites.

Both the CRM scorer (extract_crm_signals.py) and the brief generator
(backend/services/generation.py) import from here. Real API calls happen when a
credential is available; callers fall back to a deterministic stub otherwise so
the app still runs with no key.
"""

from __future__ import annotations

import os
from functools import lru_cache

# Default to the most capable current Opus model. Override with LLM_MODEL.
DEFAULT_MODEL = "claude-opus-4-8"
MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODEL)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Real calls are made when an API key is present. Force on/off with LLM_ENABLED.
LLM_ENABLED = _env_flag("LLM_ENABLED", default=bool(os.environ.get("ANTHROPIC_API_KEY")))


@lru_cache(maxsize=1)
def get_client():
    """Return a lazily-constructed, cached Anthropic client.

    The SDK reads ANTHROPIC_API_KEY (or an `ant auth login` profile) from the
    environment. It auto-retries 429/5xx/connection errors with backoff.
    """
    import anthropic

    return anthropic.Anthropic(max_retries=2, timeout=60.0)
