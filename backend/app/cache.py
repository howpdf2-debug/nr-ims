"""Valkey (Redis-compatible) client and connectivity probe."""

from typing import cast

import valkey.asyncio as valkey_async

from app.config import Settings


def build_cache(settings: Settings) -> valkey_async.Valkey:
    client = valkey_async.Valkey.from_url(
        settings.valkey_url.get_secret_value(), decode_responses=True
    )
    return cast(valkey_async.Valkey, client)


async def ping_cache(client: valkey_async.Valkey) -> None:
    await client.ping()