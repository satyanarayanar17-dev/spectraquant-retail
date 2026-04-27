# Dockerfile for Railway deploy of apps/api (FastAPI).
#
# Why a Dockerfile instead of Nixpacks?
# Nixpacks auto-detects this monorepo as Node.js because apps/web/package.json
# exists. The `providers = ["python"]` override in nixpacks.toml is not honored
# in Railway's build environment (verified across commits c1cbe57 and e547173,
# both failed at `pip: command not found`). A Dockerfile bypasses provider
# detection entirely and gives a deterministic, portable build.

FROM python:3.12-slim

# Build deps (needed by greenlet, asyncpg, statsmodels wheels on slim).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# uv is faster than pip for resolving the spectraquant-core + apps/api graph.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy only what apps/api needs at build/runtime. apps/web and infra are
# excluded via .dockerignore so they don't bust the build cache or bloat
# the image.
COPY packages/spectraquant-core ./packages/spectraquant-core
COPY apps/api ./apps/api

# Install both packages into the system Python. --system avoids needing a
# venv inside the container (the container itself is the isolation boundary).
RUN uv pip install --system --no-cache \
        -e ./packages/spectraquant-core \
        -e ./apps/api

# Railway injects $PORT at runtime; default to 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

# Match the start command we previously had in railway.json so the contract
# stays identical for the runtime.
CMD ["sh", "-c", "uvicorn src.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT}"]
