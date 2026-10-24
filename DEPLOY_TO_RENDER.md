# Deploying to Render.com

This repository is pre-configured for 1-click or repository deployment on **[Render.com](https://render.com/)**.

---

## Method 1: Blueprint Deployment (Fastest)

1. Push this repository to **GitHub**.
2. Go to your [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** > **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml` and configure:
   - **Service Type**: Web Service (Python 3.11)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --chdir web -w 1 --threads 16 -b 0.0.0.0:$PORT server:app`
6. Click **Apply**. Your 12-slot badge spoofer will be live in 1–2 minutes!

---

## Method 2: Manual Web Service

1. On the Render Dashboard, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure the settings:
   - **Name**: `unq-badge` (this assigns your URL: `unq-badge.onrender.com`)
   - **Language**: `Python 3`
   - **Region**: `Oregon (US West)` or your preferred region
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --chdir web -w 1 --threads 16 -b 0.0.0.0:$PORT server:app`
4. Click **Create Web Service**.

---

## Key Configurations for Render

- **Single Worker Process with Threading**:
  `gunicorn -w 1 --threads 16` ensures that all 12 slots share the exact same in-memory state and queue without multi-process memory fragmentation.
- **Port Binding**:
  Render injects the `PORT` environment variable. The server automatically binds to `0.0.0.0:$PORT`.
- **Bundled Games Catalog**:
  `web/games.json` is packaged with the repository, ensuring zero startup latency and no reliance on external Discord CDN downloads during deployment.
