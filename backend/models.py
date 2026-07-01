from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

class ProductFit(BaseModel):
    xT_CDx: int = Field(..., alias="xT CDx")
    xR: int
    xF_plus: int = Field(..., alias="xF+")

    class Config:
        allow_population_by_field_name = True
        alias_generator = None
        allow_population_by_alias = True

class ScoreComponent(BaseModel):
    label: str
    value: float

class CRMEntry(BaseModel):
    has_crm_data: bool
    crm_score: int | None = None
    reasoning: str | None = None
    top_objection: str | None = None
    key_interest: str | None = None

class RankedProvider(BaseModel):
    provider_id: str
    name: str
    specialty: str
    institution: str
    city: str
    state: str
    region: str
    monthly_patients: int
    addressable_patients_per_month: int
    pct_biomarker_tested: int | None = None
    product_fit: dict[str, int]
    best_fit_product: str
    product_fit_reasons: dict[str, list[str]]
    products: list[str]
    signal: str
    fit_reasons: list[str]
    crm: CRMEntry
    score: float
    score_components: list[ScoreComponent]
    weights_used: dict[str, float]

class ObjectionHandler(BaseModel):
    objection: str
    response_bullets: list[str]

class MeetingScript(BaseModel):
    headline: str
    bullets: list[str]
    suggested_close: str

class GenerationResponse(BaseModel):
    objection_handler: ObjectionHandler
    meeting_script: MeetingScript
    likely_questions: list[dict[str, Any]]
