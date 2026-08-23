#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - Unified Fullstack Startup for Render / Cloud Deploy
# Starts Nginx reverse proxy, FastAPI backend, and Nitro frontend in one container
# ==============================================================================

set -e

# Use Render/Cloud injected PORT or default to 8000
export PORT=${PORT:-8000}
envsubst '${PORT}' < /app/nginx.conf.template > /etc/nginx/nginx.conf

echo "============================================================"
echo " 🚀 Starting EdgeVision Fullstack Services"
echo " External Port: ${PORT}"
echo "============================================================"

# 1. Start Python FastAPI Backend on internal port 8080
export SERVER_PORT=8080
export SERVER_HOST=127.0.0.1
export DB_ENGINE=sqlite
export PYTHONUNBUFFERED=1
python3 -m uvicorn src.api.server:app --host 127.0.0.1 --port 8080 &
BACKEND_PID=$!

# 2. Start Frontend Nitro Server on internal port 3000
PORT=3000 node /app/frontend/.output/server/index.mjs &
FRONTEND_PID=$!

# 3. Wait briefly for services to initialize
sleep 2

echo "✅ Backend  running on 127.0.0.1:8080 (PID: $BACKEND_PID)"
echo "✅ Frontend running on 127.0.0.1:3000 (PID: $FRONTEND_PID)"
echo "🌐 Nginx reverse proxy listening on port ${PORT}..."

# 4. Start Nginx reverse proxy on external $PORT in foreground
nginx -g "daemon off;"