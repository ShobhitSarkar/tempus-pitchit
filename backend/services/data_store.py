from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import NORMALIZED_PROVIDERS_PATH, CACHED_SIGNALS_PATH, PRODUCT_KB_PATH
from extract_crm_signals import load_providers


def load_data(
    normalized_providers_path: Path = NORMALIZED_PROVIDERS_PATH,
    cached_signals_path: Path = CACHED_SIGNALS_PATH,
    product_kb_path: Path = PRODUCT_KB_PATH,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    providers = load_providers(normalized_providers_path)
    providers_by_id = {provider["provider_id"]: provider for provider in providers}
    with cached_signals_path.open("r", encoding="utf-8") as handle:
        cached_signals = json.load(handle)
    with product_kb_path.open("r", encoding="utf-8") as handle:
        product_kb = json.load(handle)
    return providers_by_id, cached_signals, product_kb
