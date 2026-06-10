# ── Stage 1: Frontend Build ───────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
# Supabase keys must be present at build time so Vite bakes them into the bundle.
ARG VITE_SUPABASE_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

# ── Stage 2: Python Runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libxml2-dev libxslt-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the Python package (dependencies + src) from pyproject.toml.
# src/ must be copied before `pip install .` because setuptools packages.find targets src*.
COPY pyproject.toml ./
COPY src/      ./src/
RUN pip install --no-cache-dir .

# Project assets (not part of the installed package)
COPY scripts/  ./scripts/
COPY data/     ./data/
COPY run_report.py ./
COPY onboarding.html ./

# Built frontend (from Stage 1)
COPY --from=frontend-builder /build/dist ./frontend/dist

RUN mkdir -p /app/data/archives /app/data/reports /app/data/mi_news

EXPOSE 8000

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
