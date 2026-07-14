# pbicompass - production image.
# Python 3.12 keeps full wheel availability for FastAPI/pydantic and the
# optional pbixray adapter. The .pbip path remains pure stdlib.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pandoc enables PDF output. HTML, DOCX, MD, and JSON work without it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends pandoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

# Web service, AI engines, Postgres, and Supabase Auth support. AI providers
# stay inert until their API keys are supplied at runtime or by BYOK upload.
RUN pip install ".[service,agents,postgres,auth]"

# Run as a non-root user. /data is only for local/self-host SQLite fallback;
# production uses Supabase Postgres and Supabase Storage.
RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app

ENV PBICOMPASS_DB=/data/pbicompass.db \
    PBICOMPASS_JOBS_DB=/data/pbicompass_jobs.db \
    PBICOMPASS_OUTPUT_STORE=memory \
    PBICOMPASS_SANDBOX_ROOT=/tmp/pbicompass \
    PBICOMPASS_MAX_UPLOAD_MB=100

EXPOSE 8000

# Cloud Run performs platform-level health management. Keep the image-level
# healthcheck disabled so local Docker and Cloud Run behave consistently.
HEALTHCHECK NONE

# Single worker: job processing is in-process. Scale out later via Celery/Redis.
# Bind to $PORT when the platform provides one, else 8000 locally.
CMD ["sh", "-c", "hypercorn pbicompass.service.app:app --bind 0.0.0.0:${PORT:-8000} --workers 1"]
