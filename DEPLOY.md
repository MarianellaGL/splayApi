# Splay Engine Deployment Guide

## Quick Deploy to Render

### Option 1: Blueprint Deploy (Recommended)

1. Fork/clone this repository to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New** → **Blueprint**
4. Connect your GitHub repo
5. Render will detect `render.yaml` and deploy automatically

### Option 2: Manual Deploy

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Configure:
   - **Name:** `splay-engine`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -e ".[api]"`
   - **Start Command:** `uvicorn splay.api.app:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (optional):
   - `SPLAY_CACHE_DIR`: `/tmp/splay_cache`
   - `ALLOWED_ORIGINS`: Your mobile app domain(s)
6. Click **Create Web Service**

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8000` |
| `SPLAY_ENV` | Environment name | `development` |
| `SPLAY_CACHE_DIR` | Directory for spec cache | System temp |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `*` |

---

## Local Development

```bash
# Clone
git clone <repo-url>
cd splay

# Install
pip install -e ".[api,dev]"

# Run
uvicorn splay.api.app:app --reload

# Test
pytest splay/tests/
```

---

## Docker Deployment

```bash
# Build
docker build -t splay-engine .

# Run
docker run -p 8000:8000 splay-engine

# With environment variables
docker run -p 8000:8000 \
  -e ALLOWED_ORIGINS="https://myapp.com" \
  -e SPLAY_CACHE_DIR="/tmp/cache" \
  splay-engine
```

---

## API Endpoints

Once deployed, access:
- **API Docs:** `https://<your-app>.onrender.com/api/docs`
- **Health Check:** `https://<your-app>.onrender.com/health`
- **OpenAPI Spec:** `https://<your-app>.onrender.com/openapi.json`

---

## Mobile App Integration

Update your mobile app to use the deployed URL:

```javascript
// React Native / Expo example
const API_BASE = "https://splay-engine.onrender.com/api/v1";

// Create session
const response = await fetch(`${API_BASE}/sessions`, {
  method: "POST",
  body: formData,
});

// Upload photo
const photoResponse = await fetch(`${API_BASE}/sessions/${sessionId}/photo`, {
  method: "POST",
  body: photoFormData,
});
```

---

## Persistence Notes

⚠️ **Render Free Tier Limitations:**
- Instance spins down after 15 minutes of inactivity
- Ephemeral filesystem (cache is lost on restart)

For production:
1. Use Render paid tier for persistent disk
2. Or accept that specs will recompile after cold starts (still cached in memory during session)

This is fine for the MVP because:
- Sessions are ephemeral anyway
- Specs can be recompiled from rules
- State is reconstructed from photos

---

## Monitoring

### Health Check

```bash
curl https://<your-app>.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "splay-engine",
  "version": "1.0.0"
}
```

### Logs

View logs in Render Dashboard → Your Service → Logs

---

## Scaling Considerations

Current architecture supports:
- Multiple concurrent sessions (in-memory)
- Stateless API (can scale horizontally)
- Session-scoped state (no shared state)

For high scale:
1. Use Redis for session storage
2. Add load balancer
3. Use persistent storage for spec cache
