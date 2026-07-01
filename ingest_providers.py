#!/usr/bin/env python3
"""Ingest provider source data into normalized JSON for the FastAPI demo backend."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

PRODUCT_FIT_REASONS = {
    "xT CDx": [
        "Broad tissue profiling supports clinical decision-making across oncology specialties.",
        "FDA-approved CDx status makes it a strong anchor for therapy selection conversations.",
    ],
    "xR": [
        "RNA fusion and splice-event detection adds complementarity when DNA testing leaves questions.",
        "Best positioned when the clinical question involves gene rearrangements or transcriptomic signals.",
    ],
    "xF+": [
        "Liquid biopsy is valuable when tissue access is limited or speed matters.",
        "Non-invasive ctDNA profiling supports rapid decision-making and serial monitoring.",
    ],
}

PRODUCT_SIGNAL_TEMPLATES = {
    "xT CDx": "Tissue NGS profiling for broad DNA decision support.",
    "xR": "RNA fusion detection and RNA-level signal for hard-to-capture alterations.",
    "xF+": "Liquid biopsy when speed, limited tissue, or serial monitoring matters.",
}


def parse_product_kb(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    sections = text.split("## ")
    kb: dict[str, dict[str, str]] = {}
    for section in sections:
        section = section.strip()
        if not section or section.startswith("#"):
            continue
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        product = lines[0]
        entry: dict[str, str] = {}
        for line in lines[1:]:
            if line.startswith("- **") and ":**" in line:
                key, value = line[3:].split(":**", 1)
                key = key.strip(" *")
                value = value.strip().lstrip("-").strip()
                entry[key] = value
        kb[product] = {
            "indication": entry.get("Indication / primary use case", ""),
            "sample_type": entry.get("Sample type required", ""),
            "tat": entry.get("Turnaround time", ""),
            "differentiator": entry.get("Key differentiator vs. other Tempus products", ""),
        }
    return kb


def load_product_fit(path: Path) -> dict[str, dict[str, int]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_provider_csv(path: Path) -> list[dict[str, Any]]:
    providers: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        all_lines = [line for line in handle if not line.lstrip().startswith("#")]
    if not all_lines:
        return providers
    reader = csv.DictReader(all_lines)
    for row in reader:
        provider_id = row.get("provider_id", "")
        if not provider_id:
            continue
        providers.append(
            {
                "provider_id": provider_id.strip(),
                "name": row["name"].strip(),
                "specialty": row["specialty"].strip(),
                "sub_specialty": row["sub_specialty"].strip(),
                "institution": row["institution"].strip(),
                "city": row["city"].strip(),
                "state": row["state"].strip(),
                "monthly_patients": int(row["monthly_patients"]) if row["monthly_patients"].strip() else None,
                "pct_biomarker_tested": int(row["pct_biomarker_tested"]) if row["pct_biomarker_tested"].strip() else None,
                "addressable_patients_per_month": int(row["addressable_patients_per_month"]) if row["addressable_patients_per_month"].strip() else None,
            }
        )
    return providers


def normalize_volume(providers: list[dict[str, Any]]) -> None:
    scores = [provider["addressable_patients_per_month"] for provider in providers if provider["addressable_patients_per_month"] is not None]
    if not scores:
        return
    # Scale relative to the highest-volume provider so every provider shows a
    # proportional bar (the busiest reads 100, none floor to a flat 0).
    max_value = max(scores) or 1
    for provider in providers:
        raw = provider.get("addressable_patients_per_month")
        provider["volume"] = {
            "normalized_score": 0.0 if raw is None else float(raw / max_value),
            "raw": raw,
        }


def build_provider_record(
    row: dict[str, Any],
    fit_map: dict[str, dict[str, int]],
    kb: dict[str, dict[str, str]],
) -> dict[str, Any]:
    specialty = row["specialty"]
    fit_scores = fit_map.get(specialty, {})
    products = sorted(fit_scores.keys(), key=lambda key: -fit_scores.get(key, 0))
    has_crm_data = row["provider_id"] != "P007" and (DATA_DIR / "crm_notes" / f"crm_notes_{row['provider_id']}.txt").is_file()
    raw_text_ref = f"crm_notes_{row['provider_id']}.txt" if has_crm_data else None
    return {
        "provider_id": row["provider_id"],
        "name": row["name"],
        "specialty": specialty,
        "sub_specialty": row["sub_specialty"],
        "institution": row["institution"],
        "city": row["city"],
        "state": row["state"],
        "region": ", ".join(part for part in (row["city"], row["state"]) if part),
        "monthly_patients": row["monthly_patients"],
        "pct_biomarker_tested": row["pct_biomarker_tested"],
        "addressable_patients_per_month": row["addressable_patients_per_month"],
        "volume": row.get("volume", {"normalized_score": 0.0, "raw": row["addressable_patients_per_month"]}),
        "product_fit": {
            "xT CDx": fit_scores.get("xT CDx", 0),
            "xR": fit_scores.get("xR", 0),
            "xF+": fit_scores.get("xF+", 0),
        },
        "product_fit_reasons": {
            product: PRODUCT_FIT_REASONS.get(product, [f"{product} complements the provider's diagnostic workflow."])
            for product in ["xT CDx", "xR", "xF+"]
        },
        "products": products,
        "signal": PRODUCT_SIGNAL_TEMPLATES.get(products[0], "High-priority biomarker testing opportunity."),
        "fit_reasons": [
            f"Strong {specialty} volume with a clear biomarker testing opportunity.",
            f"{row['addressable_patients_per_month']} addressable patients per month suggests meaningful scale.",
            f"Product fit across tissue, RNA, and liquid pathways supports a flexible conversation.",
        ],
        "crm": {
            "has_crm_data": bool(has_crm_data),
            "raw_text_ref": raw_text_ref,
            "crm_score": None,
            "reasoning": None,
            "top_objection": None,
            "key_interest": None,
        },
    }


def write_output(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ingest_providers(
    providers_csv: Path = DATA_DIR / "providers.csv",
    fit_table_json: Path = DATA_DIR / "product_fit_table.json",
    kb_markdown: Path = DATA_DIR / "product_knowledge_base.md",
    out_normalized: Path = OUTPUT_DIR / "normalized_providers.json",
    out_product_kb: Path = OUTPUT_DIR / "product_kb.json",
) -> None:
    provider_rows = load_provider_csv(providers_csv)
    fit_map = load_product_fit(fit_table_json)
    product_kb = parse_product_kb(kb_markdown)
    normalize_volume(provider_rows)

    records = [build_provider_record(row, fit_map, product_kb) for row in provider_rows]

    write_output(out_normalized, records)
    write_output(out_product_kb, product_kb)
    print(f"Wrote {out_normalized}")
    print(f"Wrote {out_product_kb}")


if __name__ == "__main__":
    ingest_providers()
