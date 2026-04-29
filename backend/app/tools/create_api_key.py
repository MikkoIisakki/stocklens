"""Mint a fresh API key and store its hash.

Usage:
    python -m app.tools.create_api_key --name pulse-mobile-prod

The raw key is printed to stdout exactly once — store it somewhere safe
(password manager, secret manager). Only the SHA-256 hash is persisted,
so a lost key cannot be recovered: revoke the row and mint a new one.

See ADR-007.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

from app.api.auth import generate_raw_key, hash_key
from app.common.config import settings
from app.storage import repository as repo


async def _run(name: str) -> None:
    raw = generate_raw_key()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    try:
        async with pool.acquire() as conn:
            key_id = await repo.insert_api_key(conn, name=name, key_hash=hash_key(raw))
    finally:
        await pool.close()

    # Print the raw key to stdout (operator captures it); send the metadata
    # to stderr so it's still visible when the caller pipes stdout to a file.
    print(raw)
    print(f"# created api_key id={key_id} name={name!r}", file=sys.stderr)
    print("# This is the ONLY time the raw key will be shown.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Pulse API key.")
    parser.add_argument(
        "--name",
        required=True,
        help="Human label for the key (e.g. 'pulse-mobile-prod', 'mikko-laptop').",
    )
    args = parser.parse_args()
    if not args.name.strip():
        parser.error("--name must be non-empty")
    asyncio.run(_run(args.name.strip()))


if __name__ == "__main__":
    main()
