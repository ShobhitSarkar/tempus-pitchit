from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

NORMALIZED_PROVIDERS_PATH = OUTPUT_DIR / "normalized_providers.json"
CACHED_SIGNALS_PATH = OUTPUT_DIR / "cached_signals.json"
PRODUCT_KB_PATH = OUTPUT_DIR / "product_kb.json"
CRM_NOTES_DIR = DATA_DIR / "crm_notes"
DIST_DIR = ROOT / "dist"

DEFAULT_WEIGHTS = {
    "w_volume": 20,
    "w_fit": 40,
    "w_engagement": 40,
}
