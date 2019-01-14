FROM python:3.6.6-slim-stretch as builder
MAINTAINER asi@dbca.wa.gov.au

# Prepare the base environment.
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3-dev \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip

# Install the project.
FROM builder
WORKDIR /app
COPY . .
RUN apt-get update -y \
  && apt-get install --no-install-recommends -y gcc libxml2-dev libxslt1-dev zlib1g-dev \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir -r requirements.txt \
  && python manage.py collectstatic --noinput
EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=10s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/catalogue/api/records/?format=json"]
CMD ["gunicorn", "csw.wsgi", "--config", "gunicorn.ini"]
