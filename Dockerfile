# pbidoc — production image.
# Python 3.12: full wheel availability for FastAPI/pydantic, and (optionally)
# pbixray for .pbix parsing. The .pbip path is pure stdlib and works anywhere.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pandoc enables PDF output (HTML/DOCX/MD/JSON work without it).
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

# Web service deps. Add engines as needed:
#   ".[service,agents]"  -> + Claude (set ANTHROPIC_API_KEY)
#   ".[service,pbix]"    -> + legacy .pbix parsing
RUN pip install ".[service]"

# Run as a non-root user; /data holds the SQLite accounts DB (mount a volume here).
RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app

ENV PBIDOC_DB=/data/pbidoc.db \
    PBIDOC_SANDBOX_ROOT=/tmp/pbidoc \
    PBIDOC_MAX_UPLOAD_MB=100
# Auth is OFF by default (public tenant). For a hosted SaaS set:
#   PBIDOC_REQUIRE_AUTH=1   (and create accounts with `pbidoc account create`)

EXPOSE 8000

# Single worker: the job store is in-process. Scale out later via Celery/Redis.
# Bind to $PORT when the platform provides one (Render/Railway), else 8000 (local/VM).
CMD ["sh", "-c", "uvicorn pbidoc.service.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
