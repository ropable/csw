# syntax=docker/dockerfile:1
# Prepare the base environment.
FROM python:3.11-slim-bookworm AS builder_base

ENV UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=1 \
  UV_PYTHON_DOWNLOADS=never \
  UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/
COPY pyproject.toml uv.lock /_lock/

# Synchronize dependencies.
# This layer is cached until uv.lock or pyproject.toml change.
RUN --mount=type=cache,target=/root/.cache \
  cd /_lock && \
  uv venv --seed && \
  uv sync --frozen --no-group dev

##################################################################################

# Prepare the base environment.
FROM python:3.11.11-slim
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/csw

RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install -y libmagic-dev gcc binutils gdal-bin proj-bin python3-dev libpq-dev gzip curl \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user.
RUN groupadd -r -g 10001 app \
  && useradd -r -u 10001 -d /app -g app -N app

COPY --from=builder_base --chown=app:app /app /app
# Make sure we use the virtualenv by default.
# Run Python unbuffered.
ENV PATH=/app/.venv/bin:$PATH \
  PYTHONUNBUFFERED=1

# Install the project.
WORKDIR /app
COPY catalogue ./catalogue
COPY csw ./csw
COPY gunicorn.py manage.py ./
RUN python manage.py collectstatic --noinput
USER app
EXPOSE 8080
CMD ["gunicorn", "csw.wsgi", "--config", "gunicorn.py"]
