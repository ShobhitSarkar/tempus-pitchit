# Tempus Sales Copilot Demo

A lightweight demo POC that ingests provider, fit, and CRM data, exposes ranked provider results and brief generation through FastAPI, and renders the experience in a React dashboard.

## Run locally

```bash
pip install -r requirements.txt
npm install
npm run build
uvicorn backend.main:app --reload --port 8000
```

Then open http://localhost:8000.

## Notes

- The backend runs deterministic ingestion and CRM-stub extraction on startup.
- Vite proxies `/api` requests to the FastAPI server during development.
- The built frontend is also served by FastAPI for the demo flow.
