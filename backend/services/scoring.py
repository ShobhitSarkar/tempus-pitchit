from __future__ import annotations

from typing import Any


def normalize_weights(w_volume: float, w_fit: float, w_engagement: float) -> tuple[float, float, float]:
    total = w_volume + w_fit + w_engagement
    if total == 0:
        return 0.0, 0.0, 0.0
    return w_volume / total, w_fit / total, w_engagement / total


def build_score_component(label: str, value: float) -> dict[str, Any]:
    return {"label": label, "value": round(value)}


def rank_providers(
    providers: dict[str, dict[str, Any]],
    cached_signals: dict[str, Any],
    w_volume: float,
    w_fit: float,
    w_engagement: float,
) -> list[dict[str, Any]]:
    w_volume, w_fit, w_engagement = normalize_weights(w_volume, w_fit, w_engagement)
    ranked: list[dict[str, Any]] = []

    for provider_id, provider in providers.items():
        volume_score = float(provider.get("volume", {}).get("normalized_score", 0.0)) * 100.0
        fit_scores = provider.get("product_fit", {}) or {}
        best_fit_product = max(fit_scores, key=lambda product: fit_scores.get(product, 0)) if fit_scores else ""
        product_fit_score = float(fit_scores.get(best_fit_product, 0))
        crm_entry = cached_signals.get(provider_id, {}).get("crm", {})
        has_crm_data = bool(crm_entry.get("has_crm_data") is True)
        engagement_score = crm_entry.get("crm_score") if has_crm_data else None

        if has_crm_data and engagement_score is not None:
            score = volume_score * w_volume + product_fit_score * w_fit + float(engagement_score) * w_engagement
            components = [
                build_score_component("Volume", volume_score),
                build_score_component("Product fit", product_fit_score),
                build_score_component("Engagement", float(engagement_score)),
            ]
            weights_for_response = {"w_volume": w_volume, "w_fit": w_fit, "w_engagement": w_engagement}
        else:
            fit_weight = 0.0 if (w_volume + w_fit) == 0 else w_fit / (w_volume + w_fit)
            volume_weight = 0.0 if (w_volume + w_fit) == 0 else w_volume / (w_volume + w_fit)
            score = (volume_score * volume_weight) + (product_fit_score * fit_weight)
            components = [
                build_score_component("Volume", volume_score),
                build_score_component("Product fit", product_fit_score),
            ]
            weights_for_response = {"w_volume": volume_weight, "w_fit": fit_weight, "w_engagement": 0.0}

        ranked.append(
            {
                "provider_id": provider_id,
                "name": provider.get("name"),
                "specialty": provider.get("specialty"),
                "institution": provider.get("institution"),
                "city": provider.get("city"),
                "state": provider.get("state"),
                "region": provider.get("region"),
                "monthly_patients": provider.get("monthly_patients"),
                "addressable_patients_per_month": provider.get("addressable_patients_per_month"),
                "pct_biomarker_tested": provider.get("pct_biomarker_tested"),
                "product_fit": fit_scores,
                "best_fit_product": best_fit_product,
                "product_fit_reasons": provider.get("product_fit_reasons", {}),
                "products": provider.get("products", []),
                "signal": provider.get("signal"),
                "fit_reasons": provider.get("fit_reasons", []),
                "crm": {
                    "has_crm_data": has_crm_data,
                    "crm_score": engagement_score,
                    "top_objection": crm_entry.get("top_objection"),
                    "key_interest": crm_entry.get("key_interest"),
                    "reasoning": crm_entry.get("reasoning"),
                },
                "score": round(score, 1),
                "score_components": components,
                "weights_used": weights_for_response,
            }
        )

    ranked.sort(key=lambda item: item["score"] or 0.0, reverse=True)
    return ranked
