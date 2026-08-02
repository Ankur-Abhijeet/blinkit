# Deployment Guide: Render (Backend) & Vercel (Frontend)

This guide provides step-by-step instructions for deploying the **Blinkit Cart Interrupt MVP**:
- **Backend API**: Hosted on **Render** (FastAPI + Groq LLM + BigBasket Dataset + Candidate Pools)
- **Frontend SPA**: Hosted on **Vercel** (HTML5/CSS3/Vanilla JS Mobile SPA)

---

## 1. Backend Deployment on Render

### Step 1.1: Push Repository to GitHub
Ensure all code changes, `requirements.txt`, `render.yaml`, `Dockerfile`, and `BigBasket Products.csv` are committed to your GitHub repository.

### Step 1.2: Create Web Service on Render
1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Web Service** (or use **Blueprints** with `render.yaml`).
3. Connect your GitHub repository: `Blinkit-MVP`.
4. Configure service settings:
   - **Name**: `blinkit-mvp-backend`
   - **Environment**: `Python 3` (or `Docker`)
   - **Region**: Singapore (or nearest region)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt && python3 -m discovery.offline.catalog_generator`
   - **Start Command**: `uvicorn discovery.api.app:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables under **Environment**:
   - `GROQ_API_KEY`: `<Your_Groq_API_Key>`
   - `PYTHON_VERSION`: `3.11.0`
6. Click **Create Web Service**.

Once deployed, Render will provide a public backend URL, e.g.:
`https://blinkit-mvp-backend.onrender.com`

---

## 2. Frontend Deployment on Vercel

### Step 2.1: Deploying via Vercel CLI or Dashboard
1. Log into your [Vercel Dashboard](https://vercel.com/).
2. Click **Add New** -> **Project**.
3. Import your GitHub repository: `Blinkit-MVP`.
4. Configure project settings:
   - **Framework Preset**: `Other` / `Static HTML`
   - **Root Directory**: `./` (or `discovery/web`)
   - **Build Command**: (Leave empty for static site)
   - **Output Directory**: `discovery/web`
5. Add Environment Variables (Optional):
   - `NEXT_PUBLIC_API_URL`: `https://blinkit-mvp-backend.onrender.com`
6. Click **Deploy**.

---

## 3. Connecting Frontend (Vercel) to Backend (Render)

The frontend automatically resolves the backend URL via `API_BASE_URL` in `discovery/web/app.js`:

1. **Local Development**: When running locally on `localhost:8000`, the app uses relative URLs (`""`).
2. **Production Deployment**: When hosted on Vercel, the app automatically targets your Render Backend URL (`https://blinkit-mvp-backend.onrender.com`).
3. **Custom Backend Override**: You can override the backend URL at runtime by setting in browser console:
   ```js
   localStorage.setItem("BLINKIT_BACKEND_URL", "https://your-custom-backend.onrender.com");
   location.reload();
   ```

---

## 4. Verification & Health Check

- **Backend Health Check**:
  `GET https://blinkit-mvp-backend.onrender.com/healthz`
  Expected output: `{"status": "ok", "service": "discovery-api"}`

- **Backend Catalog Endpoint**:
  `GET https://blinkit-mvp-backend.onrender.com/v1/catalog`
  Expected output: `{"total_count": 3000, "items": [...]}`

- **Frontend Application**:
  Open your Vercel URL (e.g. `https://blinkit-mvp.vercel.app`).
