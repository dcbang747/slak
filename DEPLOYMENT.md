# Deployment

The whole app deploys to **Vercel as a single project** — no separate backend
host, no database, free beyond the domain:

```
yourdomain.com ──► Vercel
                     ├─ Vite SPA (static)            ← frontend/dist
                     └─ FastAPI on /api/* (Python fn) ← api/index.py
```

Generation runs **synchronously** in one request (`POST /api/generate` returns the
stats, family tree, and the ZIP as base64 in a single JSON response), so the
backend is fully stateless and fits Vercel's serverless model.

---

## Layout that makes this work

| File | Role |
|---|---|
| `frontend/` | Vite SPA. Built by Vercel into `frontend/dist`. |
| `api/index.py` | Vercel Python serverless function. Mounts the FastAPI backend (`backend/app`) under `/api`. |
| `requirements.txt` (repo root) | Python deps Vercel installs for the function. |
| `vercel.json` (repo root) | Build command + output dir + `includeFiles: backend/**` + the `/api/*` rewrite. |

---

## Steps

1. **Push to GitHub.**
2. **Vercel → Add New ➜ Project → import this repo.** Leave **Root Directory =
   repo root** (the default — *not* `frontend`, because the Python function lives
   in `api/` and needs the backend code via `includeFiles`).
3. Vercel reads [`vercel.json`](vercel.json): it runs `cd frontend && npm install
   && npm run build`, serves `frontend/dist`, and deploys `api/index.py` as a
   Python function with `requirements.txt`.
4. **Deploy**, then open the `…vercel.app` URL and test: upload a name list,
   define a dynasty, Generate, download the ZIP, open the Family Tree.

### Custom domain (1-grid)
- Vercel project → **Settings ➜ Domains** → add `yourdomain.com`.
- In the **1-grid DNS panel**, add the records Vercel shows (an **A record** for
  the apex, a **CNAME** `www → cname.vercel-dns.com`). Vercel issues HTTPS
  automatically once DNS propagates.

### CORS
Same-origin (the SPA and the API share the Vercel domain), so CORS isn't needed.
The backend still honours a `CORS_ORIGINS` env var (default `*`) if you ever call
it from another origin.

---

## ⚠️ The one part not yet verified

I could test the synchronous backend and the whole flow **locally**, but not the
**Vercel Python routing** (no deploy from here). The setup follows the standard
"static SPA + `api/` Python function" pattern and the mount logic is verified
(`/api/generate` → backend `/generate`). If the first deploy returns 404s on
`/api/*`, the fix is almost always one of:

- **Path mismatch.** Vercel routes `/api/*` to `api/index.py`; the function mounts
  the backend under `/api`, so it expects to receive the original `/api/...` path.
  If Vercel instead strips it, drop the `app.mount("/api", …)` in `api/index.py`
  and expose the backend `app` directly (`from app.main import app`).
- **Backend not bundled.** Confirm `includeFiles: "backend/**"` is in
  `vercel.json` (the function imports `backend/app`).
- **Deps.** Confirm the root `requirements.txt` was picked up in the build logs.

Check the runtime logs in the Vercel dashboard — they show the import error or the
path the function actually received.

### Caveats (free tier, serverless)
- **Execution time limit** (~60s on Hobby — confirm current value). Typical runs
  are ~0.1–1s, so only extreme configs (many thousands of characters) risk it.
- **Response size:** the ZIP rides back as base64 in JSON. Fine for normal runs
  (well under ~1 MB); enormous runs could approach Vercel's response limit.
- **Cold starts** on the Python function after idle (first request slower).

---

## Local development is unchanged

`docker compose up --build` still runs everything locally — the `api/` function
and `vercel.json` are ignored locally; Docker runs `backend/app/main.py` via
uvicorn and the Vite dev server proxies `/api/*` to it (`vite.config.js`).
