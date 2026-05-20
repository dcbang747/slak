# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.
Backend details → `backend/CLAUDE.md`. Frontend details → `frontend/CLAUDE.md`.
Dev startup instructions → `STARTUP.md` (read this when the user asks to "start it" or "run it").

---

## Project Overview

**CK3 History Generator v7.0** — a web application that generates fictional medieval character and title histories in Paradox Interactive Clausewitz script format (`.txt`), ready for use as CK3 mod content.

The user uploads real CK3 mod files (title history, genetic traits, death reasons, name lists, religions, secrets), defines dynasties directly in the UI, configures a timeline of dynasty sequences per title using a Gantt chart, then triggers a simulation. The backend produces a ZIP containing Paradox script files that the CK3 game engine can parse directly.

The reference mod is a Lord of the Rings conversion mod; all `RawSampleFiles/` examples are from that mod.

The spec has two documents:
- `Jis.pdf` — original v7.0 spec (architecture, output format, simulation rules)
- `Jis_Additional.pdf` — amendment v2.0 (cadet branches, secrets, relationships, religion parsing, dynasty output files, new UI panels)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Zustand 4.5.5 |
| Backend API | FastAPI (Python 3.11+) |
| Generation | In-process `ThreadPoolExecutor` + in-memory job store (`jobs.py`) — no Celery/Redis |
| Containerisation | Docker Compose (2 services: api, frontend) |
| Output format | Paradox Clausewitz script |

---

## Commands

### Docker (recommended — full stack in one command)
```bash
docker compose up --build
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

Backend code changes require a rebuild (`--build`). For backend-only rebuilds:
```bash
docker compose up --build api
```

Frontend hot-reloads automatically via Chokidar polling (volume mount + `CHOKIDAR_USEPOLLING=true`) — no rebuild needed for frontend-only changes.

### Local backend (Python 3.11+ — no Redis needed)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Generation runs in an in-process thread pool inside the API (`jobs.py`), so there is no separate worker or broker to start.

### Local frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

No automated tests. Validate changes manually using `RawSampleFiles/`.

---

## Architecture

### Request lifecycle

```
User drops .txt file
    → POST /upload/{titles|traits|deaths|names|religions|secrets}
    → backend parses + returns preview data
    → Zustand store updates

User defines dynasties in UI (Global Settings → Dynasties panel)
    → stored in dynasty_definitions[] in Zustand — no file upload

User clicks Generate Simulation
    → store.buildPayload() serialises Zustand state → SimulationPayload JSON
    → POST /generate
    → jobs.submit_generation() queues the run on an in-process thread pool, task_id returned immediately
    → RightDrawer polls GET /status/{task_id} every 1.2 s
    → On SUCCESS: Download ZIP button appears → GET /download/{task_id}
```

### Docker service topology

```
api     (FastAPI) ← receives uploads + /generate; runs generation in a ThreadPoolExecutor (jobs.py)
                    parse → simulate → render → ZIP, results held in an in-memory job store
frontend (Vite)   ← proxies /api/* to api:8000
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RESULTS_DIR` | `tempfile.gettempdir()` | Where result ZIPs are written (same instance serves them back) |
| `GENERATION_WORKERS` | `4` | Thread-pool size for concurrent generations |
| `JOB_TTL_SECONDS` | `3600` | Finished jobs (and their ZIPs) are pruned after this |
| `VITE_API_PROXY` | `http://localhost:8000` | Frontend → backend proxy target (Docker overrides to `http://api:8000`) |

On Windows, generated ZIPs land in `C:\Users\<user>\AppData\Local\Temp\`.

---

## Windows 10 Local Setup

No Redis or message broker is required — generation runs inside the API process.

**Option A — Docker Desktop (recommended):**
1. Enable WSL2: `wsl --install` (admin, reboot)
2. Install Docker Desktop (admin)
3. `docker compose up --build` — no further admin needed

**Option B — native Python/Node:**
1. `winget install Python.Python.3.12` and `winget install OpenJS.NodeJS.LTS` (admin)
2. Backend: `uvicorn app.main:app --reload --port 8000`; frontend: `npm run dev`

Admin is only required for initial toolchain installation. All daily dev commands run without elevation.

---

## Critical Coupling Points

Changes in one place **require** matching changes in the other:

| If you change… | You must also update… |
|---|---|
| Fields in `SimulationPayload` or nested schemas | `store.buildPayload()` in `store.js` |
| `/status/{task_id}` response shape in `main.py` | `RightDrawer.jsx` (reads `data.state`, `data.message`, `data.result.*`, `data.error`) |
| `_pick_name()` key convention | `extract_name_lists()` key format |
| Vite proxy path prefix (`/api`) | All `api.js` fetch calls + FastAPI route paths |
| Output ZIP contents in `jobs.py` | Download handling in `RightDrawer.jsx` |
| `DynastyDefinition` schema fields | Dynasty card UI in `GlobalSettings.jsx` + `store.js` defaults + `buildPayload()` |
| `GlobalSettings` schema fields | `store.js` `global_settings` initial state + `buildPayload()` |
| Personality trait exclusion groups in `schemas.py` | `_defaultPersonalityTraits()` in `store.js` (must mirror exactly) |
| Dynasty ID renamed in `updateDynastyDef` | `title_sequences` entries are automatically rewritten — this is handled in the store action |

---

## Known Gaps (design limitations, not bugs)

| Item | Detail |
|---|---|
| `maximum_generations` | Simulation checks it but interacts with per-title sequence config — a single long sequence can exhaust all generations before timeline ends |
| Bastard system | Fully implemented; bastards have no title succession rights (by design) |
| S3 output | `boto3` in `requirements.txt` but never used; ZIPs go to `RESULTS_DIR` (local temp) |
| Traits preview | Parsed and stored; no frontend view — used only during simulation |
| Death reasons | Hardcoded by trait/age in `mortality.py` (no upload needed); the `/upload/deaths` endpoint + `deaths_txt` field still exist but are unused |
| Title history `government`/`liege` | `DynastySequence` has `government_type` and `liege_title_id` fields but `output.py` does not yet write them to title history blocks |
| `/upload/dynasties` endpoint | Still exists in `main.py` but the frontend no longer calls it — dynasties are user-defined via the UI |

---

## Explicitly Out of Scope (spec mandate)

Do not add: culling mechanics, dynamic nicknames, 3D DNA strings.

Cadet branches, secrets, and relationships are **in scope** via `Jis_Additional.pdf`.
