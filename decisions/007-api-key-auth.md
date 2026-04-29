# ADR-007: API key authentication, JWT deferred

**Date**: 2026-04-29
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

Phase 3 mandates an auth layer (task 3.3) before the white-label
mobile/web shells (3.2/3.5) and push notifications (3.4) can land. Until
this ADR, the REST API was open — anyone with the URL could read
electricity prices, alerts, and (eventually) personal user state.

Two auth shapes were on the table:

1. **API keys only** — one secret per app/operator, header-auth, no
   per-user state.
2. **API keys *and* JWT for end users** — needed when individual users
   have personal state (saved alert subscriptions, watchlists, push
   tokens registered to a specific account).

The Phase 7.1 candidate for first public release is the electricity
app. It currently has **no per-user state** — all data is regional
(prices, alerts) or device-local (push token, app settings). JWT for
end users would be premature scaffolding.

## Decision

Adopt **API keys only** for now. JWT for end users is explicitly
deferred until a feature actually needs per-user server state.

### Mechanics

- **Token format**: `pulse_<32 hex chars>` (16 bytes of `secrets.token_hex`,
  + a 6-char prefix). The prefix makes keys recognisable in logs and
  triggers gitleaks if accidentally committed.
- **Storage**: only the lowercase hex SHA-256 digest is persisted, in
  `api_key (id, name, key_hash, created_at, last_used_at, revoked_at)`.
  Plain SHA-256 (not bcrypt) is appropriate because the key already
  carries 128 bits of cryptographic randomness; bcrypt's slow-hash
  property buys nothing against a brute-force search of that space.
- **Lookup**: O(1) on a partial unique index over `key_hash WHERE
  revoked_at IS NULL`.
- **Master key**: `Settings.master_api_key` bypasses the DB lookup when
  set. Intended for local dev and bootstrap (the first key has to come
  from somewhere). Compared with `secrets.compare_digest` to avoid
  timing leaks. Empty string disables the path entirely so production
  deployments that don't set it are not implicitly bypassable.
- **Issuance**: `python -m app.tools.create_api_key --name <label>`
  generates a random key, inserts the hash, and prints the raw key to
  stdout exactly once. The operator stores it in a password manager.
  A lost key is unrecoverable: revoke and reissue.
- **Revocation**: set `revoked_at` rather than deleting the row, so
  `last_used_at` history is preserved for audit.
- **Header**: `Authorization: Bearer pulse_…`. Standard. Returns
  `WWW-Authenticate: Bearer` on 401 so clients see the contract.

### Where it applies

Wired at router-include time in `main.py`:

| Path prefix | Authenticated? | Why |
|---|---|---|
| `/v1/health/*` | No | Load balancer, Grafana, oncall need to probe without provisioning credentials. |
| `/v1/assets/*` | Yes | Stocks domain data. |
| `/v1/energy/*` | Yes | Electricity domain data. |

Adding a new domain router automatically inherits no auth — opt-in is
explicit at `app.include_router(..., dependencies=[Depends(require_api_key)])`.
This is intentional: a future internal/diagnostic router should not
silently leak data because a developer forgot to add the dep.

### Per-call cost

- Master path: 1 constant-time string compare. No DB.
- DB path: one `SELECT id, name FROM api_key WHERE key_hash = $1 AND
  revoked_at IS NULL` (covered by `api_key_active_lookup_idx`) plus one
  `UPDATE api_key SET last_used_at = now()`. ~2ms typical.

The `last_used_at` write doubles per-request DB load — acceptable
because traffic is low and the ops value (spotting unused / leaked
keys) is high. Revisit if QPS grows enough that this matters.

## Alternatives considered

### Bearer JWT for both apps and users now

Rejected as premature. JWT requires picking a signing algorithm,
managing key rotation, deciding on token lifetime, refresh-token
flow, and probably an `auth/login` endpoint — all complexity that buys
nothing while the only client is a mobile app reading public regional
data.

### HTTP Basic with username/password

Rejected. Easier for humans to leak in shell history (`curl -u`),
harder to revoke individually (changing the password rotates everyone),
and doesn't compose with the future "issue a key per device" pattern.

### Bcrypt-hash the keys

Rejected. The key is 128 random bits. SHA-256 is already
cryptographically irreversible against that input space; bcrypt's
work-factor adds no security and adds ~50ms per request.

### One key per env var (no DB table)

Rejected. Doesn't support multiple keys per environment (mobile prod,
web prod, mikko-laptop, ops-readonly), revocation requires a deploy,
no `last_used_at` audit. The master-key env var preserves this
ergonomic for the bootstrap case only.

## Consequences

**Positive**:

- Endpoints that handle data are protected; health stays open for
  probes.
- Operators can issue, label, audit, and revoke keys without touching
  code.
- The path to JWT-for-users is additive: layer a second dependency on
  the routers that need user identity, leave `require_api_key` in
  place.
- Mobile shells (task 3.2) get a clear contract: ship one
  `MASTER_API_KEY` per build profile, or fetch a per-install key from
  the operator's onboarding endpoint (future work).

**Negative / trade-offs**:

- Existing API tests built FastAPI apps with the router included
  directly (no auth wiring) — they keep passing because they bypass
  `main.create_app()`. A separate `test_auth.py` covers the production
  wiring.
- `last_used_at` write per request — see "Per-call cost" above.
- Revocation is eventually-consistent across the asyncpg pool's
  prepared-statement caches if the row is updated from outside (psql).
  Acceptable: revocation matters in human time, not millisecond time.

**Revisit when**:

- A feature requires per-user state on the server — add JWT alongside
  API keys, scope routes that need it.
- The API serves multiple tenants and key issuance becomes
  self-service — add an admin endpoint backed by `insert_api_key`.
- QPS grows past ~1k/s and the `last_used_at` write is hot — drop it
  to once-per-minute via a cache, or remove it and rely on access logs.

## References

- Task 3.3 in `docs/PLAN.md`.
- ADR-001 (modular monolith): the auth dep lives in
  `backend/app/api/auth.py`, importable from any router.
- `backend/app/tools/create_api_key.py` for issuance.
- `db/migrations/005_api_key.sql` for the schema.
