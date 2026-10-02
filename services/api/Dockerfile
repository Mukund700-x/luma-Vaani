# ─── Base ─────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ─── Builder ──────────────────────────────────────────────────────────────────
FROM base AS builder
RUN pip install --upgrade pip
COPY pyproject.toml .
RUN pip install -e ".[dev]"

# ─── Development (hot-reload) ─────────────────────────────────────────────────
FROM builder AS development
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ─── Production ───────────────────────────────────────────────────────────────
FROM base AS production
RUN pip install --upgrade pip
COPY pyproject.toml .
RUN pip install -e "."
COPY . .
# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
