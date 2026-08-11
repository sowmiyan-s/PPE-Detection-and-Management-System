# ── Stage 1: Build Frontend ──
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Unified Production Environment ──
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (OpenCV, Nginx, Node.js runtime, envsubst)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    nginx \
    gettext-base \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend source code and models
COPY src/ ./src/
COPY models/ ./models/
COPY experiments/ ./experiments/
COPY database/ ./database/
COPY bytetrack.yaml ./

# Copy built Frontend output from Stage 1
COPY --from=frontend-builder /app/frontend/.output ./frontend/.output
COPY --from=frontend-builder /app/frontend/package.json ./frontend/package.json

# Copy Nginx template and startup script
COPY nginx.conf.template ./
COPY start_render.sh ./
RUN chmod +x /app/start_render.sh

# Environment variables
ENV SERVER_HOST=127.0.0.1
ENV SERVER_PORT=8000
ENV PORT=8000

EXPOSE 8000

CMD ["/app/start_render.sh"]
