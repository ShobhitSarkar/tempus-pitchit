from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import (
    CACHED_SIGNALS_PATH,
    CRM_NOTES_DIR,
    DIST_DIR,
    NORMALIZED_PROVIDERS_PATH,
    DEFAULT_WEIGHTS,
)
from backend.services.data_store import load_data
from backend.services.generation import build_generation_response
from backend.services.notes import add_note, get_notes
from backend.services.scoring import rank_providers
from extract_crm_signals import extract_crm_signals
from ingest_providers import ingest_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    ingest_providers()
    extract_crm_signals(NORMALIZED_PROVIDERS_PATH, CRM_NOTES_DIR, CACHED_SIGNALS_PATH)
    providers_by_id, cached_signals, product_kb = load_data()
    app.state.providers_by_id = providers_by_id
    app.state.cached_signals = cached_signals
    app.state.product_kb = product_kb
    yield


app = FastAPI(title="Tempus Sales Copilot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/providers/ranked")
def get_ranked_providers(
    w_volume: float = Query(DEFAULT_WEIGHTS["w_volume"], ge=0),
    w_fit: float = Query(DEFAULT_WEIGHTS["w_fit"], ge=0),
    w_engagement: float = Query(DEFAULT_WEIGHTS["w_engagement"], ge=0),
) -> list[dict[str, object]]:
    providers_by_id = getattr(app.state, "providers_by_id", {})
    cached_signals = getattr(app.state, "cached_signals", {})
    if not providers_by_id:
        raise HTTPException(status_code=503, detail="Server not ready")
    return rank_providers(providers_by_id, cached_signals, w_volume, w_fit, w_engagement)


@app.post("/api/providers/{provider_id}/generate")
def generate_for_provider(provider_id: str) -> dict[str, object]:
    providers_by_id = getattr(app.state, "providers_by_id", {})
    cached_signals = getattr(app.state, "cached_signals", {})
    product_kb = getattr(app.state, "product_kb", {})
    provider = providers_by_id.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    crm_entry = cached_signals.get(provider_id, {}).get("crm", {})
    best_fit_product = max(provider.get("product_fit", {}), key=lambda p: provider["product_fit"].get(p, 0))
    provider_with_best_fit = {**provider, "best_fit_product": best_fit_product}
    return build_generation_response(provider_with_best_fit, crm_entry, product_kb)


@app.get("/api/providers/{provider_id}/notes")
def list_provider_notes(provider_id: str) -> dict[str, object]:
    providers_by_id = getattr(app.state, "providers_by_id", {})
    if provider_id not in providers_by_id:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"provider_id": provider_id, "notes": get_notes(provider_id)}


@app.post("/api/providers/{provider_id}/notes")
def create_provider_note(provider_id: str, text: str = Body(..., embed=True)) -> dict[str, object]:
    providers_by_id = getattr(app.state, "providers_by_id", {})
    if provider_id not in providers_by_id:
        raise HTTPException(status_code=404, detail="Provider not found")
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Note text cannot be empty")
    return {"provider_id": provider_id, "notes": add_note(provider_id, cleaned)}


@app.get("/")
def index() -> FileResponse:
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend build not found")


if DIST_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    index_path = DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")
