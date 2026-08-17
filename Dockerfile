# syntax=docker/dockerfile:1

# ---- Builder stage: compiliers and libraries ----
FROM dhi.io/python:3.11-debian13-dev AS builder

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  gcc \
  g++ \
  libgdal-dev \
  libmagic-dev \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY catalogue ./catalogue
COPY csw ./csw
COPY gunicorn.py manage.py pyproject.toml uv.lock ./

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/
RUN uv sync \
  --no-group dev \
  --link-mode=copy \
  --compile-bytecode \
  --no-python-downloads \
  --frozen \
  && rm -rf /bin/uv uv.lock

RUN uv pip install "setuptools<=80.10.2"
ENV PATH="/app/.venv/bin:$PATH"
RUN python -m compileall -q catalogue csw \
  && python manage.py collectstatic --noinput

# ---- runtime stage: minimal packages needed to run the application ----
FROM dhi.io/python:3.11-debian13-dev AS runtime
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/csw

RUN apt-get update && apt-get install -y --no-install-recommends \
  gdal-bin \
  proj-bin \
  libgdal36 \
  libmagic1t64 \
  libpq5 \
  gzip \
  # Run shared library linker after installing spatial packages
  && ldconfig \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app /app

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

USER nonroot
EXPOSE 8080
CMD ["gunicorn", "csw.wsgi", "--config", "gunicorn.py"]
