# Deployment

Two pieces, both free:

```
yourdomain.com ──► Vercel (React SPA) ──/api/*──► Render (FastAPI backend)
   (1-grid DNS)                          rewrite
```

- **Frontend** → Vercel (static Vite build).
- **Backend** → Render free web service (single FastAPI process; generation runs
  in an in-process thread pool — no Redis/worker).
- **Domain** → bought at 1-grid, pointed at Vercel.

Recurring cost: just the domain.

---

## 1. Push to GitHub

Make sure this repo is on GitHub (Render and Vercel both deploy from it).

---

## 2. Backend on Render

1. Render Dashboard → **New ➜ Blueprint** → connect this repo.
2. Render reads [`render.yaml`](render.yaml) and proposes the
   `ck3-history-generator-api` service (free, Docker, root dir `backend`). Click
   **Apply**.
3. Wait for the first deploy (a few minutes). Render builds `backend/Dockerfile`
   and starts it (`uvicorn` binds Render's injected `$PORT` automatically).
4. Copy the service URL, e.g. `https://ck3-history-generator-api.onrender.com`.
   Confirm it's up: visiting `…/health` returns `{"status":"ok"}`.

**Free-tier behaviour:** the service sleeps after ~15 min idle and cold-starts
(~30–60s) on the next request — the first person to use it after a quiet spell
waits a bit. Results (in-memory jobs + ZIPs) are ephemeral, which is fine because
generate → download happens within seconds. Keep it to **one instance** (no
autoscaling): results live in that process's memory.

---

## 3. Frontend on Vercel

1. Edit [`frontend/vercel.json`](frontend/vercel.json) and replace
   `REPLACE-WITH-YOUR-RENDER-URL.onrender.com` with your Render host from step 2.
   Commit + push.
   - This rewrites same-origin `/api/*` calls to the backend and strips the
     `/api` prefix (matching the backend's route names). Same-origin means **no
     CORS issues**.
2. Vercel Dashboard → **Add New ➜ Project** → import this repo.
3. Set **Root Directory** to `frontend` (Vercel then auto-detects Vite).
4. Deploy. You'll get a `…vercel.app` URL — open it and confirm uploads +
   Generate work end to end.

> Alternative to the rewrite: instead of `vercel.json`, set a Vercel env var
> `VITE_API_BASE=https://<render-host>` and the SPA will call the backend
> directly. That path needs CORS (step 5) since it's cross-origin. The rewrite is
> simpler — prefer it.

---

## 4. Point the 1-grid domain at Vercel

1. Vercel project → **Settings ➜ Domains** → add `yourdomain.com`.
2. Vercel shows the DNS records to create. In the **1-grid DNS panel**, add them:
   - Apex (`yourdomain.com`): the **A record** Vercel gives (or an ALIAS/ANAME if
     1-grid supports it).
   - `www`: a **CNAME** to `cname.vercel-dns.com`.
3. Wait for DNS to propagate; Vercel issues HTTPS automatically.

The backend stays on its `…onrender.com` URL — it doesn't need a custom domain
(you can add `api.yourdomain.com` later if you want).

---

## 5. Lock down CORS (before sharing publicly)

The backend defaults to `CORS_ORIGINS=*`. Once the domain is live, set it to your
real origin so only your site can call the API:

- Render → your service → **Environment** → set
  `CORS_ORIGINS=https://yourdomain.com` (comma-separate multiple origins) → save
  (it redeploys).

> Note: if you used the **vercel.json rewrite** (step 3), browser calls are
> same-origin and CORS isn't strictly required — but setting it is still good
> hygiene and protects the `…vercel.app` and direct-URL cases.

---

## Local development is unchanged

`docker compose up --build` still runs everything locally (the Dockerfile falls
back to port 8000 when `$PORT` isn't set, and `api.js` falls back to `/api` via
the Vite proxy when `VITE_API_BASE` isn't set).
