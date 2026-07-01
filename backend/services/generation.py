from __future__ import annotations

import sys
from typing import Any

from pydantic import BaseModel

from llm import LLM_ENABLED, MODEL, get_client

GENERATION_SYSTEM = """You are a sales-enablement assistant for reps who sell Tempus oncology
diagnostics (xT CDx tissue profiling, xR RNA fusion detection, xF+ liquid biopsy).

Write a concise, credible pre-call brief for a single provider, grounded ONLY in
the facts the user gives you (provider profile, best-fit product and its key
metrics, and CRM signals). Do not invent clinical claims, numbers, or product
capabilities that are not provided.

Produce:
- objection_handler: the provider's most likely objection and 2-3 crisp bullets
  the rep can say to address it.
- meeting_script: a one-line headline, 2-4 short pitch bullets (each a line the
  rep could actually say), and a suggested_close question.
- likely_questions: exactly 3 questions the provider is likely to ask, each with
  a short intent label and 1-2 answerBullets of speaking notes.

Keep every line specific to this provider and product. Be direct and practical."""


class _ObjectionHandler(BaseModel):
    objection: str
    response_bullets: list[str]


class _MeetingScript(BaseModel):
    headline: str
    bullets: list[str]
    suggested_close: str


class _LikelyQuestion(BaseModel):
    question: str
    intent: str
    answerBullets: list[str]


class _Brief(BaseModel):
    objection_handler: _ObjectionHandler
    meeting_script: _MeetingScript
    likely_questions: list[_LikelyQuestion]


def _build_context(
    provider: dict[str, Any],
    crm_entry: dict[str, Any],
    product_kb: dict[str, Any],
) -> str:
    best_fit = provider.get("best_fit_product") or "xT CDx"
    kb = product_kb.get(best_fit, {})
    lines = [
        f"Provider: {provider.get('name')}",
        f"Specialty: {provider.get('specialty')}",
        f"Institution: {provider.get('institution')}",
        f"Addressable patients / month: {provider.get('addressable_patients_per_month')}",
        f"% biomarker tested: {provider.get('pct_biomarker_tested')}",
        f"Product fit scores (0-100): {provider.get('product_fit')}",
        f"Best-fit product: {best_fit}",
        f"  - indication: {kb.get('indication', 'n/a')}",
        f"  - sample type: {kb.get('sample_type', 'n/a')}",
        f"  - turnaround time: {kb.get('tat', 'n/a')}",
        f"  - key differentiator: {kb.get('differentiator', 'n/a')}",
    ]
    if crm_entry.get("has_crm_data") is False or not crm_entry:
        lines.append("CRM signals: none on file for this provider.")
    else:
        lines.append(f"CRM top objection: {crm_entry.get('top_objection') or 'none noted'}")
        lines.append(f"CRM key interest: {crm_entry.get('key_interest') or 'none noted'}")
        lines.append(f"CRM reasoning: {crm_entry.get('reasoning') or 'n/a'}")
    return "\n".join(lines)


def _llm_response(
    provider: dict[str, Any],
    crm_entry: dict[str, Any],
    product_kb: dict[str, Any],
) -> dict[str, Any]:
    """Generate a brief with a real Anthropic call using structured output."""
    response = get_client().messages.parse(
        model=MODEL,
        max_tokens=2048,
        system=GENERATION_SYSTEM,
        messages=[{"role": "user", "content": _build_context(provider, crm_entry, product_kb)}],
        output_format=_Brief,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError("model refused or returned no structured output")
    return response.parsed_output.model_dump()


def _template_response(
    provider: dict[str, Any],
    crm_entry: dict[str, Any],
    product_kb: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic template used when the LLM is disabled or a call fails."""
    best_fit = provider.get("best_fit_product") or "xT CDx"
    kb = product_kb.get(best_fit, {})
    objection = crm_entry.get("top_objection") or "Need more clarity on the current decision workflow."
    key_interest = crm_entry.get("key_interest") or "speed and clinical confidence"
    sample_type = kb.get("sample_type", "clinical sample")
    tat = kb.get("tat", "standard turnaround")
    differentiator = kb.get("differentiator", "a strong clinical differentiator")

    objection_handler = {
        "objection": objection,
        "response_bullets": [
            f"Acknowledge the concern and show how {best_fit} is built for that use case.",
            f"Highlight {sample_type} workflow and {tat} for quicker clarity.",
            f"Frame it as a differentiated option because of {differentiator.lower()}",
        ],
    }

    meeting_script = {
        "headline": f"Position {best_fit} as the right fit for {provider.get('specialty')} with {sample_type}",
        "bullets": [
            f"Lead with the provider's interest in {key_interest}.",
            f"Connect to the product's {tat} and how it eases decision-making.",
            f"Tie the recommendation back to the provider's current biomarker / tissue workflow.",
        ],
        "suggested_close": "Ask for one recent case where current testing speed or tissue access delayed a treatment decision.",
    }

    likely_questions = [
        {
            "question": objection,
            "intent": "Primary concern",
            "answerBullets": [
                f"Use the question to pivot to {best_fit}'s workflow advantages.",
                f"Point out the {tat} and sample requirements to reduce uncertainty.",
            ],
        },
        {
            "question": f"How will {best_fit} fit into my current ordering process?",
            "intent": "Workflow fit",
            "answerBullets": [
                f"Explain the sample path: {sample_type} submission and clinical reporting cadence.",
                "Emphasize a clean handoff from ordering to result interpretation.",
            ],
        },
        {
            "question": "What makes this product different from the current vendor?",
            "intent": "Differentiator",
            "answerBullets": [
                f"Call out the product's differentiator: {differentiator}",
                "Keep the focus on clinical confidence and faster insight for treatment decisions.",
            ],
        },
    ]

    return {
        "objection_handler": objection_handler,
        "meeting_script": meeting_script,
        "likely_questions": likely_questions,
    }


def build_generation_response(
    provider: dict[str, Any],
    crm_entry: dict[str, Any],
    product_kb: dict[str, Any],
) -> dict[str, Any]:
    """Build a call brief, preferring a real LLM call and degrading to the template."""
    if LLM_ENABLED:
        try:
            return _llm_response(provider, crm_entry, product_kb)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully on any API failure
            print(
                f"WARNING: LLM brief generation failed for "
                f"{provider.get('provider_id')}: {exc}. Falling back to template.",
                file=sys.stderr,
            )
    return _template_response(provider, crm_entry, product_kb)
