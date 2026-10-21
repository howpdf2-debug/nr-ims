FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    NRIMS_IN_CONTAINER=true

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first (cached until pyproject.toml changes).
RUN pip install --upgrade pip "setuptools>=68" wheel
COPY pyproject.toml constraints.txt ./
RUN python - <<'PY' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
PY
# constraints.txt pins every transitive version -> identical builds everywhere (`make lock` to refresh)
RUN pip install -c constraints.txt -r /tmp/req.txt && rm /tmp/req.txt

# Application + migrations + ops scripts (previously missing -> `alembic` could not run).
COPY alembic.ini entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app
COPY arq_worker.py ./
COPY seed_admin.py seed_master.py seed_data.py seed_links.py seed_inventory.py simulate_fault.py ./

RUN sed -i 's/\r$//' /app/entrypoint.sh \
 && useradd --create-home --shell /usr/sbin/nologin nrims \
 && chmod +x /app/entrypoint.sh \
 && chown -R nrims:nrims /app
USER nrims

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
