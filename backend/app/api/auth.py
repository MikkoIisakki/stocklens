"""API key authentication.

Single FastAPI dependency, ``require_api_key``, attached at router-include
time so individual route authors don't have to remember to wire it.

Authentication contract:
    Authorization: Bearer pulse_<32 hex chars>

Resolution order:
    1. Master key (settings.master_api_key) — used in dev/bootstrap.
    2. SHA-256 hash lookup in the api_key table where revoked_at IS NULL.
    3. 401 Unauthorized otherwise.

We never store the raw key — only its hex SHA-256 digest. Plain hash (not
bcrypt) is appropriate because the keys are 128 bits of cryptographic
randomness; brute force on the hash is no easier than brute force on the
key itself, and the lookup must be O(1) per request.

See ADR-007.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from app.api.dependencies import Pool
from app.common.config import Settings
from app.common.config import settings as default_settings
from app.storage import repository as repo

KEY_PREFIX = "pulse_"
_BEARER_PREFIX = "Bearer "


def hash_key(raw_key: str) -> str:
    """Return the lowercase hex SHA-256 digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_raw_key() -> str:
    """Generate a fresh random API key with the platform prefix.

    Used by the create_api_key CLI; tests can call it directly to mint
    keys against a real DB.
    """
    return KEY_PREFIX + secrets.token_hex(16)


def get_settings() -> Settings:
    """Dependency — overridable in tests."""
    return default_settings


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header (expected 'Bearer <key>')",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[len(_BEARER_PREFIX) :].strip()


async def require_api_key(
    pool: Pool,
    cfg: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Validate the request's API key.

    Returns a dict identifying the caller (``{"id": int|None, "name": str}``)
    so route handlers can audit-log who did what. Raises 401 on missing,
    malformed, unknown, or revoked keys.
    """
    raw_key = _extract_bearer(authorization)

    master = cfg.master_api_key.get_secret_value()
    if master and secrets.compare_digest(raw_key, master):
        return {"id": None, "name": "master"}

    digest = hash_key(raw_key)
    async with pool.acquire() as conn:
        row = await repo.lookup_api_key(conn, digest)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        await repo.touch_api_key_last_used(conn, row["id"])

    return {"id": row["id"], "name": row["name"]}
