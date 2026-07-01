# Deployment & Tradeoffs

**Goal:** one shared instance running somewhere, so people can open a URL and click
around. This is a POC — several choices here trade robustness for "get it live in an
afternoon." Those tradeoffs are documented on purpose.

> Companion doc: open [`how-it-works.html`](how-it-works.html) in a browser for a
> visual tour of how the app is put together.

---

## What we're deploying

One process. `uvicorn backend.main:app` serves **both** the built React UI (from
`dist/`) and the `/api` endpoints. No separate frontend host and no database. The
two AI features (CRM scoring, brief generation) make **real Anthropic API calls
when `ANTHROPIC_API_KEY` is set**, and fall back to a deterministic stub/template
when it isn't. See `how-it-works.html` §1.

That shape is why this is easy to host: it's a single container/process with one port.

### One env var to decide behaviour

| `ANTHROPIC_API_KEY` | What runs | Cost |
|---------------------|-----------|------|
| **set** | Real model calls (`claude-opus-4-8` by default; override with `LLM_MODEL`) | Per-token, on your Anthropic account |
| **unset** | Deterministic stub scores + templated briefs — app still fully works | Free |

Set it as a secret in the host's dashboard (Railway/Render both have a secrets UI).
Force the stub path even with a key present via `LLM_ENABLED=0`.

---

## Recommended approach: one container on Railway (or Render)

A tiny multi-stage `Dockerfile` (Node stage builds `dist/`, Python stage runs
uvicorn) sidesteps the "needs both Node and Python" wrinkle and runs the same
everywhere.

**Steps**

1. Add a `Dockerfile` + `.dockerignore`.
2. Push the repo to GitHub.
3. On Railway/Render: *New → Deploy from GitHub repo* (auto-detects the Dockerfile).
4. It builds and gives a public URL.

**Effort:** ~30–45 min, mostly first-time account clicking. Only code change needed
is making the start command bind `0.0.0.0` and the host's `$PORT` (currently
hardcoded to `8000`).

**Lower-effort shortcut:** build `dist/` locally, commit it (it's gitignored today),
and deploy as a native Python service — start command
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. No Node on the host. ~15 min,
but you rebuild+commit on every UI change.

---

## Tradeoffs we're accepting for the POC

| # | Choice | Why it's fine for a POC | What it costs / when it bites |
|---|--------|-------------------------|-------------------------------|
| 1 | **Ephemeral filesystem** — "Log CRM note" writes to disk | Notes last for the session; nobody depends on them | Notes are **wiped on every redeploy/restart**. Fix: attach a persistent disk, or move notes to a DB. |
| 2 | **Single worker** | One instance, low traffic | In-memory data + unlocked file writes break with multiple workers. Don't run `-w 4`. |
| 3 | **AI calls run at startup / per request** | Simple; no separate job to manage | With a key set, the 7 CRM scores are computed on **every boot** (a few seconds + token cost), and each "Generate Brief" is a live call. Fine for a demo; would be cached/moved offline for real. Without a key it's instant and free. |
| 4 | **Data files, no database** | 7 providers; nothing to administer | Doesn't scale past a small fixed dataset; edits mean redeploying. |
| 5 | **Startup recomputes CRM scores on each boot** | One code path; always fresh | With a key set this is 7 live calls per restart (see #3). The scorer is already a standalone script (`extract_crm_signals.py`) — the real fix is to run it offline and cache the result, so boots don't pay for it. |
| 6 | **CORS wide open (`*`)** | Same-origin serving, so it's not actually used | Should be tightened/removed before anything real. |
| 7 | **No auth** | It's a demo link | Anyone with the URL can use it and log notes. Add a basic gate if the link is shared widely. |

---

## Known limitations (accepted, not bugs)

- **One instance, no redundancy.** If it restarts, there's a few-seconds blip and
  in-session notes are gone (see #1).
- **No persistence guarantees.** Treat everything as disposable demo state.
- **No monitoring/alerting.** You find out it's down by visiting it.

---

## What changes for a "real" version

Not in scope now, but the path is mapped: config/secrets layer, move CRM scoring
offline, make brief-generation async with a fallback, tighten CORS, add a note-write
lock (or a DB), input length caps, and basic tests. Those are the hardening steps —
ask if/when we want to pick one up.

---

## Your notes / understanding

> _Space for you to add your own take — anything below is yours to edit._

-
-
-
