#!/usr/bin/env python3
"""
Offline CRM signal extraction for the Tempus Sales Copilot prototype.

Reads provider CRM note references from normalized_providers.json (produced by
the ingestion layer), scores each eligible provider once, and writes
cached_signals.json for downstream scoring/generation endpoints.

This is a one-time, manually-run script — not a service. Do not call from
request handlers.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm import LLM_ENABLED, structured_complete

CRM_SCORE_SYSTEM = """You are scoring a single oncology provider's sales-readiness based on CRM notes
from a medical device/diagnostics sales rep.

Read the CRM notes the user provides and produce a single "engagement readiness"
score from 0-100, plus supporting fields. Base the score on three criteria:

1. Product usage signal — Is there evidence the provider already uses, has used,
   or has expressed direct interest in a Tempus product? Higher usage/positive
   experience = higher score.
2. Competitor sentiment — Does the provider express frustration, dissatisfaction,
   or complaints about a competing product or service? Negative competitor
   sentiment = higher score (it signals an opening).
3. Receptiveness — Based on how the rep describes the interaction, how open,
   engaged, or receptive was the provider to the sales conversation? More
   receptive = higher score.

Weigh all three together into one composite judgment — do not just average three
sub-scores mechanically; use judgment about which signals are strongest in this
specific note.

Also extract:
- reasoning: a 1-2 sentence justification citing specific notes content.
- top_objection: the single clearest concern or objection raised, in the
  provider's own terms (null if none is present).
- key_interest: what this provider seems to care about most (turnaround time,
  sensitivity, cost, ease of use, etc.), based only on what's in the notes.

crm_score must be an integer between 0 and 100."""


class _CrmScore(BaseModel):
    crm_score: int
    reasoning: str
    top_objection: str | None = None
    key_interest: str | None = None


_POSITIVE_SIGNALS = (
    "interested",
    "excited",
    "great call",
    "frustrated with current",
    "wants",
    "faster turnaround",
    "switch",
    "trial",
    "pilot",
    "follow up",
    "follow-up",
    "impressed",
    "ready to",
    "champion",
    "expand",
)
_NEGATIVE_SIGNALS = (
    "not interested",
    "no budget",
    "happy with current",
    "declined",
    "no thanks",
    "cancel",
    "stick with",
    "too expensive",
)


def _stub_score(provider_id: str, crm_text: str) -> dict[str, Any]:
    """Deterministic, note-aware placeholder used when the LLM is disabled.

    A stable per-provider baseline is nudged up/down by simple sentiment signals
    in the notes, so logging a note visibly changes the score on the next
    startup — this makes the self-improvement loop demonstrable without an API
    key. Fully deterministic, so scores are repeatable across restarts.
    """
    rng = random.Random(provider_id)
    base = rng.randint(35, 60)
    text = (crm_text or "").lower()
    positives = sum(text.count(signal) for signal in _POSITIVE_SIGNALS)
    negatives = sum(text.count(signal) for signal in _NEGATIVE_SIGNALS)
    score = max(0, min(100, base + 9 * positives - 13 * negatives))

    sample_objections = [
        "Turnaround time concerns for STAT cases",
        "Cost relative to current provider",
        "Unfamiliar with panel breadth",
        None,
    ]
    sample_interests = [
        "Fast turnaround for treatment-planning decisions",
        "Broader biomarker coverage",
        "Ease of ordering / integration with EMR",
        "Comparable performance data vs. current vendor",
    ]
    return {
        "crm_score": score,
        "reasoning": (
            f"[heuristic] Baseline {base} adjusted by {positives} positive / "
            f"{negatives} negative signal(s) in the notes."
        ),
        "top_objection": rng.choice(sample_objections),
        "key_interest": rng.choice(sample_interests),
    }


def _llm_score(crm_text: str) -> dict[str, Any]:
    """Score a note with a real LLM call using structured output."""
    parsed = structured_complete(
        system=CRM_SCORE_SYSTEM,
        user=f"CRM notes:\n---\n{crm_text}\n---",
        schema=_CrmScore,
        max_tokens=1024,
    )
    return {
        "crm_score": parsed.crm_score,
        "reasoning": parsed.reasoning,
        "top_objection": parsed.top_objection,
        "key_interest": parsed.key_interest,
    }


def score_crm_notes(provider_id: str, crm_text: str, *, retry: bool = False) -> dict:
    """Score one provider's CRM notes.

    Uses a real Anthropic call when the LLM is enabled (an API key is present),
    and falls back to the deterministic stub when it is disabled or the call
    fails — so extraction never crashes the app on a transient API error.
    """
    del retry  # structured output makes the JSON-reminder retry unnecessary
    if not LLM_ENABLED:
        return _stub_score(provider_id, crm_text)
    try:
        return _llm_score(crm_text)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any API failure
        print(
            f"WARNING: LLM CRM scoring failed for provider_id={provider_id}: {exc}. "
            "Falling back to stub.",
            file=sys.stderr,
        )
        return _stub_score(provider_id, crm_text)


def validate_crm_score_response(data: dict[str, Any]) -> None:
    """Validate parsed LLM response shape and crm_score range."""
    required_fields = ("crm_score", "reasoning", "top_objection", "key_interest")
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    score = data["crm_score"]
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(f"crm_score must be an integer, got {score!r}")
    if not 0 <= score <= 100:
        raise ValueError(f"crm_score must be between 0 and 100, got {score}")

    if not isinstance(data["reasoning"], str):
        raise ValueError("reasoning must be a string")

    for field in ("top_objection", "key_interest"):
        value = data[field]
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{field} must be a string or null")


def score_crm_notes_with_validation(
    provider_id: str, crm_text: str
) -> dict[str, Any]:
    """
    Call score_crm_notes once, validate, and retry once on parse/validation failure.

    When score_crm_notes is swapped for a real LLM call, this wrapper handles
    strict JSON parsing, range checks, and loud per-provider failures.
    """
    last_error: Exception | None = None
    last_raw: str | None = None

    for attempt in range(2):
        retry = attempt > 0
        try:
            result = score_crm_notes(provider_id, crm_text, retry=retry)
            validate_crm_score_response(result)
            return result
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if isinstance(exc, json.JSONDecodeError):
                last_raw = exc.doc
            continue

    print(
        f"ERROR: CRM scoring failed for provider_id={provider_id}",
        file=sys.stderr,
    )
    if last_raw is not None:
        print(f"Raw response:\n{last_raw}", file=sys.stderr)
    elif last_error is not None:
        print(f"Validation error: {last_error}", file=sys.stderr)
    raise RuntimeError(f"CRM scoring failed for provider_id={provider_id}") from last_error


def load_providers(path: Path) -> list[dict[str, Any]]:
    """Load provider records from normalized_providers.json."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "providers" in payload:
            providers = payload["providers"]
            if not isinstance(providers, list):
                raise ValueError("'providers' must be a list")
            return providers
        return [
            {"provider_id": provider_id, **record}
            for provider_id, record in payload.items()
        ]
    raise ValueError("normalized_providers.json must be a list or object")


def resolve_crm_path(raw_text_ref: str, crm_dir: Path | None) -> Path:
    """Resolve a CRM notes file path from raw_text_ref and optional crm_dir."""
    ref_path = Path(raw_text_ref)
    if ref_path.is_absolute():
        return ref_path
    if crm_dir is not None:
        return crm_dir / ref_path
    return ref_path


def provider_has_crm_data(provider: dict[str, Any]) -> bool:
    crm = provider.get("crm") or {}
    if crm.get("has_crm_data") is not True:
        return False
    return bool(crm.get("raw_text_ref"))


def null_crm_entry() -> dict[str, Any]:
    return {
        "crm": {
            "has_crm_data": False,
            "crm_score": None,
            "reasoning": None,
            "top_objection": None,
            "key_interest": None,
        }
    }


def scored_crm_entry(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "crm": {
            "has_crm_data": True,
            "crm_score": score["crm_score"],
            "reasoning": score["reasoning"],
            "top_objection": score["top_objection"],
            "key_interest": score["key_interest"],
        }
    }


def extract_crm_signals(
    normalized_providers_path: Path,
    crm_dir: Path | None,
    out_path: Path,
) -> tuple[int, int]:
    providers = load_providers(normalized_providers_path)
    output: dict[str, Any] = {}
    processed = 0
    skipped = 0

    for provider in providers:
        provider_id = provider.get("provider_id")
        if not provider_id:
            raise ValueError("Each provider record must include provider_id")

        if not provider_has_crm_data(provider):
            output[provider_id] = null_crm_entry()
            skipped += 1
            continue

        raw_text_ref = provider["crm"]["raw_text_ref"]
        crm_path = resolve_crm_path(raw_text_ref, crm_dir)
        if not crm_path.is_file():
            raise FileNotFoundError(
                f"CRM notes file not found for {provider_id}: {crm_path}"
            )

        crm_text = crm_path.read_text(encoding="utf-8")
        score = score_crm_notes_with_validation(provider_id, crm_text)
        output[provider_id] = scored_crm_entry(score)
        processed += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")

    return processed, skipped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract CRM engagement signals into cached_signals.json"
    )
    parser.add_argument(
        "--normalized-providers",
        type=Path,
        required=True,
        help="Path to normalized_providers.json from the ingestion layer",
    )
    parser.add_argument(
        "--crm-dir",
        type=Path,
        default=None,
        help="Base directory for CRM note paths in raw_text_ref (when relative)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output path for cached_signals.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.normalized_providers.is_file():
        print(
            f"ERROR: normalized providers file not found: {args.normalized_providers}",
            file=sys.stderr,
        )
        return 1

    processed, skipped = extract_crm_signals(
        args.normalized_providers,
        args.crm_dir,
        args.out,
    )

    total = processed + skipped
    print(f"Providers total: {total}")
    print(f"Providers processed (CRM scored): {processed}")
    print(f"Providers skipped (no CRM data): {skipped}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
