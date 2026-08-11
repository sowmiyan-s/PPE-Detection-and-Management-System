#!/bin/bash
set -e

# Fallback PORT to 8000 if not set
export PORT=${PORT:-8000}
echo "Starting EdgeVision Unified Fullstack Container on PORT ${PORT}..."

# Substitute $PORT into Nginx configuration
envsubst '${PORT}' < /app/nginx.conf.template > /etc/nginx/nginx.conf

# Start Python FastAPI backend on internal port 8000
echo "Starting FastAPI Backend on 127.0.0.1:8000..."
uvicorn src.api.server:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Start Frontend Nitro SSR Server on internal port 3000
echo "Starting React Frontend (Nitro SSR) on 127.0.0.1:3000..."
PORT=3000 HOST=127.0.0.1 node /app/frontend/.output/server/index.mjs &
FRONTEND_PID=$!

# Function to handle process termination
cleanup() {
    echo "Shutting down processes..."
    kill -TERM $BACKEND_PID 2>/dev/null || true
    kill -TERM $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start Nginx in foreground
echo "Starting Nginx Reverse Proxy on port ${PORT}..."
nginx -g 'daemon off;'
