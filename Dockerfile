# syntax=docker/dockerfile:1
# Args to centralise versions.
ARG PYTHON_VERSION=3.11-slim-bookworm

# ---- Builder stage ----
FROM python:${PYTHON_VERSION} AS builder

RUN <<EOF
apt-get update
apt-get install -y --no-install-recommends \
  gcc \
  g++
EOF

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --frozen

# ---- Runtime stage ----
FROM python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.title="ibms" \
  org.opencontainers.image.description="Catalogue Service Web" \
  org.opencontainers.image.source="https://github.com/dbca-wa/csw" \
  org.opencontainers.image.vendor="DBCA" \
  org.opencontainers.image.authors="asi@dbca.wa.gov.au"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

# Create a non-root user.
RUN groupadd -r -g 10001 app \
  && useradd -r -u 10001 -d /app -g app -N app

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder --chown=app:app /app /app

# Copy the remaining project files to finish building the project
COPY --chown=app:app gunicorn.py manage.py pyproject.toml ./
COPY --chown=app:app catalogue ./catalogue
COPY --chown=app:app csw ./csw

# Compile scripts and collect static files
RUN <<EOF
python -m compileall manage.py catalogue csw
python manage.py collectstatic --noinput
EOF

# Run project as the non-root user
USER app
EXPOSE 8080
CMD ["gunicorn", "csw.wsgi", "--config", "gunicorn.py"]
