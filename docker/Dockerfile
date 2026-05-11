# ── Stage 1: Frontend Build ───────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG VITE_PIN_KEY
ENV VITE_PIN_KEY=$VITE_PIN_KEY
RUN npm run build

# ── Stage 2: Python Runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libxml2-dev libxslt-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps from pyproject.toml
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Project source
COPY src/      ./src/
COPY scripts/  ./scripts/
COPY data/     ./data/
COPY run_report.py ./

# Built frontend (from Stage 1)
COPY --from=frontend-builder /build/dist ./frontend/dist

RUN mkdir -p /app/data/archives /app/data/reports /app/data/mi_news

EXPOSE 8000

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
