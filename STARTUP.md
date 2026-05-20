# Dev Startup Guide (for Claude)

This file tells Claude exactly how to start the local dev environment for this project.
Read it whenever the user asks to "start it", "run it", "spin it up", etc.

---

## Environment (verified 2026-05-18)

| Tool | Status | Version |
|---|---|---|
| Docker Desktop | ✅ Installed & running | 29.4.3 |
| WSL2 | ✅ Active (docker-desktop distro) | v2 |
| Node.js | ✅ Installed (not needed for Docker path) | v22.19.0 |
| Python | ✅ Installed (not needed for Docker path) | 3.13.9 |

**No admin access required for any of the commands below** — Docker Desktop is already running as a background service.

---

## How to start

Run these two commands in sequence. The second one blocks — leave it running.

```powershell
# Step 1 — navigate to project root
cd "C:\Users\Jaco\Documents\GitHub\slak"

# Step 2 — build and start both services (API, Frontend)
docker compose up --build
```

First run takes 3–5 minutes (downloads base images, installs Python + Node deps).
Subsequent runs take ~30 seconds.

**The stack is ready when you see this line in the output:**
```
frontend-1  |   ➜  Local:   http://localhost:5173/
```

---

## URLs (click to open)

| Service | URL |
|---|---|
| **Frontend (main app)** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **Swagger UI (API docs)** | http://localhost:8000/docs |

---

## How to stop

Press `Ctrl+C` in the running terminal, then:

```powershell
docker compose down
```

`docker compose down` removes the containers cleanly. Result ZIPs are stored in a named Docker volume (`results`) and survive restarts.

---

## Checking Docker is running before start

If `docker compose up` fails immediately with "Cannot connect to Docker daemon":

```powershell
# Open Docker Desktop
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# Wait ~15 seconds, then re-run docker compose up --build
```

---

## What each service does

| Container | Role |
|---|---|
| `api-1` | FastAPI on port 8000 — handles uploads, `/generate`, and runs the simulation in an in-process thread pool (`jobs.py`) |
| `frontend-1` | Vite dev server on port 5173 — serves the React UI, proxies `/api/*` to api:8000 |

---

## Rebuild after backend code changes

Backend code changes require a container rebuild. Frontend hot-reloads automatically via Chokidar polling — no rebuild needed for frontend-only edits.

```powershell
# Rebuild only the backend (faster than full rebuild)
docker compose up --build api

# Or rebuild everything
docker compose up --build
```

---

## Test files

`RawSampleFiles/` contains real LotR CK3 mod files for manual testing:

| Dropzone | Folder |
|---|---|
| Title History | `RawSampleFiles/TitleHistory/` |
| Genetic Traits | `RawSampleFiles/TraitFiles/` |
| Name Lists | `RawSampleFiles/NameListFiles/` |
| Religions | `RawSampleFiles/Religions/` |

Dynasties are **not uploaded from file** — they are defined directly in the UI under Global Settings → Dynasties panel.

Minimum to enable Generate button: **Title History + Name Lists**.
