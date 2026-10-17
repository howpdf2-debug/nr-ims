FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and pre-install build tooling BEFORE the package install,
# so pip can use --no-build-isolation and avoid a second PyPI round-trip.
RUN pip install --upgrade pip "setuptools>=68" wheel

COPY pyproject.toml ./
RUN pip install --no-build-isolation .

COPY app ./app

RUN useradd --create-home --shell /usr/sbin/nologin nrims \
 && chown -R nrims:nrims /app
USER nrims

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
