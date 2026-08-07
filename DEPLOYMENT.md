# Deployment Guide — Permanent Public Hosting (100% free, no credit card)

Two independent services, both connect directly to the GitHub repo (no tokens/secrets to manage): the **backend** (FastAPI + models) on **Render** (free web service), and the **frontend** (static React build) on **Vercel** (free).

## Why this combination

- Hugging Face Spaces' Docker/compute tier now requires a paid PRO plan (checked live — no longer free).
- Render's free web service tier (512MB RAM) needs no credit card, but can't fit the 670MB BERT model alongside PyTorch's own memory overhead. The deployed backend therefore runs with **`ENABLE_BERT=false`** — only the CNN2D model (~12MB, ~92% accuracy) serves predictions on the public link. BERT stays fully available when running locally (`ENABLE_BERT` defaults to `true`).
- Render's free tier spins a service down after 15 minutes of no traffic; the next request wakes it up (takes ~30-60 seconds the first time, instant after).

## Part 1 — Backend on Render

1. Create a free account: https://dashboard.render.com/register — sign up with GitHub (no card required for the free tier).
2. Authorize Render to access the `reviews` repository when prompted.
3. **New → Web Service** → select `radwaelashry30-crypto/reviews`.
4. Fill in:
   - **Name**: `olist-marketplace-backend` (or anything)
   - **Region**: closest to you
   - **Branch**: `main`
   - **Root Directory**: leave blank (repo root)
   - **Runtime**: **Docker**
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Docker Build Context Directory**: `.` (the repo root)
   - **Instance Type**: **Free**
5. Under **Environment Variables**, add:
   - `ENABLE_BERT` = `false`
   - `ENVIRONMENT` = `production`
   - `FRONTEND_ORIGINS` = `["http://localhost:5173"]` (placeholder for now — update in Part 3 once the Vercel URL exists)
6. Click **Create Web Service**. First build takes 5-10 minutes (installs PyTorch etc). Watch progress in the **Logs** tab.
7. Once it shows "Live", your backend URL is at the top of the page, e.g. `https://olist-marketplace-backend.onrender.com`.
8. Test it: open `https://olist-marketplace-backend.onrender.com/api/v1/health` — should show `{"success":true,...}`.

## Part 2 — Frontend on Vercel

1. Create a free account: https://vercel.com/signup — sign up with GitHub, authorize access to the `reviews` repo.
2. **Add New → Project** → import `radwaelashry30-crypto/reviews`.
3. **Root Directory**: click **Edit** and set it to `frontend` (important).
4. **Environment Variables**: add
   - `VITE_API_BASE_URL` = `https://olist-marketplace-backend.onrender.com/api/v1` (your actual Render URL from Part 1, step 7)
5. Click **Deploy**.
6. You'll get a permanent URL like `https://reviews-xyz.vercel.app` — **this is the link to share with anyone.**

## Part 3 — Close the loop: allow the frontend's domain in the backend's CORS

1. Back on Render → your service → **Environment** tab → edit `FRONTEND_ORIGINS`:
   - `["https://reviews-xyz.vercel.app"]` (your actual Vercel URL from Part 2, step 6 — valid JSON array syntax, no trailing slash)
2. Save — Render redeploys automatically. Wait for "Live".

## Verifying it all works

Open the Vercel URL from anywhere (phone, another PC, a friend) → Dashboard should load real numbers → Sentiment page (select **CNN2D** in the model dropdown) should return real predictions.

## Updating the deployment later

Both Render and Vercel auto-redeploy on every push to `main` on GitHub — no manual steps needed after this initial setup.

## If you ever want BERT on the public link too

Upgrade the Render service to an instance type with at least 2GB RAM (Standard, $25/month) and set `ENABLE_BERT=true`. Everything else stays the same.
