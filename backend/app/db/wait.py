"""Wait for Postgres and explain *why* it is unreachable.

    python -m app.db.wait              # wait up to NRIMS_DB_WAIT_SECONDS (default 60)
    python -m app.db.wait --diagnose   # one-shot diagnosis, exit 0/1

Distinguishes the four failure modes that all look like "it hangs":
  DNS error    -> wrong service name in the URL
  refused      -> right host, nothing listening / wrong port
  timeout      -> packets dropped: wrong network, firewall, wrong IP
  auth error   -> volume was initialised with a different password
"""

import asyncio
import os
import socket
import sys
import time

import asyncpg
from sqlalchemy.engine import make_url

from app.config import get_settings


def _classify(host: str, port: int) -> str:
    try:
        addrs = {str(a[4][0]) for a in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        return f"DNS FAILED for '{host}' ({exc}). Service name in URL is wrong or not on this network."
    for addr in addrs:
        try:
            with socket.create_connection((addr, port), timeout=3):
                return f"TCP OK to {addr}:{port}"
        except ConnectionRefusedError:
            return f"TCP REFUSED by {addr}:{port}: reachable but nothing listening (wrong port / DB not up)."
        except TimeoutError:
            return f"TCP TIMEOUT to {addr}:{port}: packets dropped (wrong network/IP/firewall, or loopback)."
        except OSError as exc:
            return f"TCP error to {addr}:{port}: {exc}"
    return "no address"


async def _try(settings) -> str | None:
    url = make_url(settings.database_url.get_secret_value())
    try:
        conn = await asyncpg.connect(
            host=url.host, port=url.port or 5432, user=url.username, password=url.password,
            database=url.database, ssl=False, timeout=5,
        )
        await conn.close()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def main() -> int:
    settings = get_settings()
    url = make_url(settings.database_url.get_secret_value())
    host, port = url.host or "", url.port or 5432
    print(f"[db-wait] target = {settings.redacted_database_url}", flush=True)
    deadline = time.monotonic() + (0 if "--diagnose" in sys.argv else
                                   float(os.getenv("NRIMS_DB_WAIT_SECONDS", "60")))
    while True:
        err = asyncio.run(_try(settings))
        if err is None:
            print("[db-wait] database is accepting connections", flush=True)
            return 0
        print(f"[db-wait] {err or 'unknown'}\n[db-wait] {_classify(host, port)}", flush=True)
        if time.monotonic() >= deadline:
            return 1
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
