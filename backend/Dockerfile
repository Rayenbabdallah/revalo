# Revalo API. Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres --no-install-project

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/src ./src
RUN uv sync --frozen --no-dev --extra postgres

# Sample files: the "try a real job" gallery and the demo seed.
COPY samples ./samples

ENV PATH=/app/.venv/bin:$PATH \
    REVALO_SAMPLES_DIR=/app/samples \
    REVALO_STORAGE_DIR=/data/files

RUN useradd --system --uid 10001 revalo && mkdir -p /data/files && chown -R revalo /data
USER revalo
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Behind Caddy: trust its X-Forwarded-* headers, so cookies are marked Secure on HTTPS.
CMD ["uvicorn", "revalo.api.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
