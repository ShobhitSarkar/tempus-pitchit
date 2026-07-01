from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import CRM_NOTES_DIR, OUTPUT_DIR

# Structured, append-only log of rep-authored notes, keyed by provider_id.
# Kept separate from the seeded CRM note text so it survives ingestion reruns.
CRM_ACTIVITY_PATH = OUTPUT_DIR / "crm_activity.json"


def _load_activity() -> dict[str, list[dict[str, Any]]]:
    if not CRM_ACTIVITY_PATH.is_file():
        return {}
    with CRM_ACTIVITY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_activity(activity: dict[str, list[dict[str, Any]]]) -> None:
    CRM_ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CRM_ACTIVITY_PATH.open("w", encoding="utf-8") as handle:
        json.dump(activity, handle, indent=2)
        handle.write("\n")


def get_notes(provider_id: str) -> list[dict[str, Any]]:
    return _load_activity().get(provider_id, [])


def add_note(provider_id: str, text: str, author: str | None = None) -> list[dict[str, Any]]:
    """Append a rep note to the structured activity log and the CRM note file."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {"timestamp": timestamp, "author": author or "Sales rep", "text": text}

    activity = _load_activity()
    activity.setdefault(provider_id, []).append(entry)
    _save_activity(activity)

    # Mirror the note into the raw CRM note file so it is written back "to the CRM".
    note_file: Path = CRM_NOTES_DIR / f"crm_notes_{provider_id}.txt"
    note_file.parent.mkdir(parents=True, exist_ok=True)
    with note_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{timestamp}] {entry['author']}: {text}\n")

    return activity[provider_id]
