# --- Build stage ---------------------------------------------------------
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# --- Runtime stage -------------------------------------------------------
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_PORT=8080

# Run as a non-root user — defense in depth on Cloud Run.
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app
COPY static ./static

USER app
EXPOSE 8080

# Cloud Run sends SIGTERM on revision shutdown; uvicorn handles it cleanly.
CMD exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "${PORT}" \
        --workers 2 \
        --proxy-headers \
        --forwarded-allow-ips="*"
