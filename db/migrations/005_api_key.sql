-- Migration: 005_api_key
-- Description: API key authentication — store a SHA-256 hash, never the raw key
-- Applies to: all environments
-- Idempotent: safe to re-run; uses CREATE TABLE IF NOT EXISTS.
--
-- See ADR-007. Keys look like 'pulse_<32 hex chars>' so they are easy to spot
-- in logs and trip gitleaks if accidentally committed.

BEGIN;

CREATE TABLE IF NOT EXISTS api_key (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT           NOT NULL,                       -- human label, e.g. 'pulse-mobile-prod'
    key_hash        TEXT           NOT NULL,                       -- hex-encoded SHA-256 of the raw key
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,                                   -- NULL = active

    CONSTRAINT api_key_key_hash_uq UNIQUE (key_hash),
    CONSTRAINT api_key_name_not_empty CHECK (length(trim(name)) > 0)
);

CREATE INDEX IF NOT EXISTS api_key_active_lookup_idx
    ON api_key (key_hash) WHERE revoked_at IS NULL;

COMMENT ON TABLE  api_key              IS 'Authentication tokens for the REST API. Never stores the raw secret.';
COMMENT ON COLUMN api_key.key_hash     IS 'Lowercase hex-encoded SHA-256 digest of the raw token. Lookup column.';
COMMENT ON COLUMN api_key.last_used_at IS 'Updated on every successful auth — useful for spotting unused / leaked keys.';
COMMENT ON COLUMN api_key.revoked_at   IS 'Set to revoke a key without deleting the row (audit trail).';

COMMIT;
