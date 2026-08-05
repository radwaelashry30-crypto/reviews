# Deployment Guide — Permanent Public Hosting

Two independent services: the **backend** (FastAPI + models, needs real RAM) on **Hugging Face Spaces** (free, 16GB RAM, Docker), and the **frontend** (static React build) on **Vercel** (free).

Common free hosts (Render/Railway/Fly free tiers) were ruled out: they cap free-tier RAM around 512MB, well under what's needed to load the 670MB BERT model into memory alongside PyTorch's own overhead.

## Part 1 — Backend on Hugging Face Spaces

1. Create a free account at https://huggingface.co/join (if you don't have one).
2. Go to https://huggingface.co/new-space
   - **Space name**: anything, e.g. `olist-marketplace-backend`
   - **SDK**: choose **Docker**
   - **Hardware**: default free `CPU basic` (2 vCPU, 16GB RAM) is enough
   - **Visibility**: Public (so the link is shareable)
   - Click **Create Space**
3. Get a write access token: https://huggingface.co/settings/tokens → **New token** → role **Write** → copy it.
4. In the **GitHub** repo (github.com/radwaelashry30-crypto/reviews) → **Settings → Secrets and variables → Actions**:
   - Add a **secret** named `HF_TOKEN` = the token from step 3.
   - Add a **variable** named `HF_SPACE_URL` = `https://huggingface.co/spaces/<your-hf-username>/<space-name>` (from step 2's URL).
5. Push anything to `main` (or go to the GitHub repo's **Actions** tab → "Sync backend to Hugging Face Space" → **Run workflow**). This runs `.github/workflows/sync-to-hf-spaces.yml`, which mirrors the repo to your Space and triggers a build there.
6. Wait for the build to finish on the Space's **Logs** tab (first build downloads PyTorch etc., can take 5-10 minutes). Once it says "Running", your backend is live at:
   `https://<your-hf-username>-<space-name>.hf.space`
7. Test it: open `https://<your-hf-username>-<space-name>.hf.space/api/v1/health` in a browser — should show `{"success":true,...}`.

## Part 2 — Frontend on Vercel

1. Create a free account at https://vercel.com/signup, sign in with GitHub, authorize access to the `reviews` repo.
2. **Add New → Project** → import `radwaelashry30-crypto/reviews`.
3. **Root Directory**: set to `frontend` (important — the repo root is not the frontend app).
4. **Environment Variables**: add
   - `VITE_API_BASE_URL` = `https://<your-hf-username>-<space-name>.hf.space/api/v1` (from Part 1, step 6)
5. Click **Deploy**. Vercel auto-detects the Vite framework and runs `npm run build`.
6. You'll get a permanent URL like `https://reviews-xyz.vercel.app` — **this is the link to share with anyone.**

## Part 3 — Close the loop: allow the frontend's domain in the backend's CORS

1. On the Hugging Face Space → **Settings → Variables and secrets** → add a **variable**:
   - `FRONTEND_ORIGINS` = `["https://reviews-xyz.vercel.app"]` (your actual Vercel URL from Part 2, step 6 — valid JSON array syntax, no trailing slash)
2. The Space restarts automatically when a variable changes. Wait for it to go back to "Running".

## Verifying it all works

Open the Vercel URL from anywhere (phone, another PC, ask a friend) → Dashboard should load real numbers → Sentiment page should return real predictions.

## Updating the deployment later

- **Backend**: any push to `main` on GitHub re-triggers the sync workflow → rebuilds the Space automatically.
- **Frontend**: any push to `main` on GitHub auto-redeploys on Vercel (no action needed).

## Costs

Both services are free at this scale. Hugging Face Spaces free CPU tier has no time limit but may sleep after a period of no traffic on some plans — a visit wakes it back up (may take a few seconds). Vercel's free tier has no sleep behavior for static sites.
