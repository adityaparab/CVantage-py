# syntax=docker/dockerfile:1
# CVantage single-container image (issue #100): build the SPA, then serve it from
# FastAPI (gunicorn + uvicorn workers) on one port.

# ---- Stage 1: build the React SPA ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ---- Stage 2: Python backend runtime ----
FROM python:3.11-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    ENVIRONMENT=production \
    SERVE_SPA=true \
    SPA_DIST_DIR=/app/frontend/dist \
    PORT=8000

WORKDIR /app/server

# Install dependencies first (cached unless the lockfile changes).
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code, then finalize the environment.
COPY server/ ./
RUN uv sync --frozen --no-dev

# The built SPA from stage 1 (served by FastAPI at SPA_DIST_DIR).
COPY --from=frontend /app/frontend/dist /app/frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health/ready').status==200 else 1)"

CMD ["uv", "run", "gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
