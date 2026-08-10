# --- Frontend Builder Stage ---
FROM --platform=$BUILDPLATFORM node:22-alpine AS frontend-builder

# Copy frontend files
COPY frontend /app/frontend

# Build frontend
WORKDIR /app/frontend
# pnpm 10+/11 默认拦截依赖 postinstall（esbuild 等），需显式允许
RUN corepack enable pnpm && \
    pnpm config set dangerouslyAllowAllBuilds true && \
    pnpm install --frozen-lockfile && \
    pnpm build

# --- Python Dependencies Stage ---
FROM --platform=$BUILDPLATFORM python:3.10.17-slim-bullseye AS python-deps

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY backend/requirements.txt /requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /requirements.txt

# --- Final Stage ---
FROM python:3.10.17-slim-bullseye

# Environment variables
ENV HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    WS_PORT=8765 \
    FRONTEND_PORT=3000 \
    TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Caddy using architecture-aware binary download
RUN ARCH=$(dpkg --print-architecture) && \
    case "$ARCH" in \
        amd64) CADDY_ARCH="amd64" ;; \
        arm64) CADDY_ARCH="arm64" ;; \
        armhf) CADDY_ARCH="armv7" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    curl -L "https://github.com/caddyserver/caddy/releases/download/v2.7.6/caddy_2.7.6_linux_${CADDY_ARCH}.tar.gz" -o caddy.tar.gz && \
    tar -xzf caddy.tar.gz && \
    mv caddy /usr/local/bin/ && \
    chmod +x /usr/local/bin/caddy && \
    rm caddy.tar.gz

# Copy Python packages from python-deps stage
COPY --from=python-deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy frontend build from frontend-builder stage
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy backend files
COPY backend /app/backend
COPY Caddyfile /app/

# Copy and set permissions for startup script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Set working directory
WORKDIR /app

# Expose port
EXPOSE 80

# Startup command
ENTRYPOINT ["/bin/bash", "/app/docker-entrypoint.sh"]
