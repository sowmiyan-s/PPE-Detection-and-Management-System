FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build

EXPOSE 3000

# Start the nitro server (default output location for tanstack start cloudflare/node)
# Since we didn't specify nitro config explicitly in vite.config.ts, the default node output is usually .output/server/index.mjs
CMD ["sh", "-c", "PORT=${PORT:-3000} node .output/server/index.mjs"]

