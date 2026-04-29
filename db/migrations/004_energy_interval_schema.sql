-- Migration: 004_energy_interval_schema
-- Description: Switch energy_price and energy_alert from (price_date, hour) to interval-based time series (ADR-005)
-- Applies to: all environments
-- DESTRUCTIVE: drops energy_price.{price_date,hour} and energy_alert.peak_hour after backfill
--              (existing rows backfilled to interval_start as hourly cadence; see ADR-005)
-- Idempotent: safe to re-run; uses IF (NOT) EXISTS guards throughout.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- energy_price — interval-based time series
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE energy_price
    ADD COLUMN IF NOT EXISTS interval_start   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS interval_end     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS interval_minutes INT;

-- Backfill from the legacy (price_date, hour) columns only when they still exist.
-- Uses EXECUTE so the planner doesn't try to resolve price_date/hour on a fresh
-- DB where those columns have never existed (CI scenario).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'energy_price' AND column_name = 'price_date'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'energy_price' AND column_name = 'hour'
    ) THEN
        EXECUTE $sql$
            UPDATE energy_price
               SET interval_start   = (price_date::timestamp + (hour || ' hours')::interval) AT TIME ZONE 'UTC',
                   interval_end     = ((price_date::timestamp + (hour || ' hours')::interval) AT TIME ZONE 'UTC') + INTERVAL '1 hour',
                   interval_minutes = 60
             WHERE interval_start IS NULL
        $sql$;
    END IF;
END $$;

ALTER TABLE energy_price
    ALTER COLUMN interval_start   SET NOT NULL,
    ALTER COLUMN interval_end     SET NOT NULL,
    ALTER COLUMN interval_minutes SET NOT NULL;

ALTER TABLE energy_price DROP CONSTRAINT IF EXISTS energy_price_region_date_hour_uq;
ALTER TABLE energy_price DROP CONSTRAINT IF EXISTS energy_price_hour_check;
DROP INDEX IF EXISTS energy_price_region_date_idx;

ALTER TABLE energy_price DROP COLUMN IF EXISTS price_date;
ALTER TABLE energy_price DROP COLUMN IF EXISTS hour;

-- New constraints. Postgres lacks IF NOT EXISTS for ADD CONSTRAINT, so guard via DO blocks.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'energy_price_region_interval_uq') THEN
        ALTER TABLE energy_price
            ADD CONSTRAINT energy_price_region_interval_uq UNIQUE (region_code, interval_start);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'energy_price_interval_minutes_positive') THEN
        ALTER TABLE energy_price
            ADD CONSTRAINT energy_price_interval_minutes_positive CHECK (interval_minutes > 0);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'energy_price_interval_end_after_start') THEN
        ALTER TABLE energy_price
            ADD CONSTRAINT energy_price_interval_end_after_start CHECK (interval_end > interval_start);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS energy_price_region_date_idx
    ON energy_price (region_code, ((interval_start AT TIME ZONE 'UTC')::date) DESC, interval_start);

COMMENT ON COLUMN energy_price.interval_start   IS 'UTC start of the price slot. PK part with region_code.';
COMMENT ON COLUMN energy_price.interval_end     IS 'UTC end of the price slot (exclusive).';
COMMENT ON COLUMN energy_price.interval_minutes IS 'Width of the slot in minutes (1, 5, 15, 60, 1440). ENTSO-E PT15M zones store 15.';


-- ─────────────────────────────────────────────────────────────────────────────
-- energy_alert — peak_hour → peak_interval_start
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE energy_alert ADD COLUMN IF NOT EXISTS peak_interval_start TIMESTAMPTZ;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'energy_alert' AND column_name = 'peak_hour'
    ) THEN
        EXECUTE $sql$
            UPDATE energy_alert
               SET peak_interval_start = (price_date::timestamp + (peak_hour || ' hours')::interval) AT TIME ZONE 'UTC'
             WHERE peak_interval_start IS NULL
        $sql$;
    END IF;
END $$;

ALTER TABLE energy_alert ALTER COLUMN peak_interval_start SET NOT NULL;

ALTER TABLE energy_alert DROP CONSTRAINT IF EXISTS energy_alert_peak_hour_check;
ALTER TABLE energy_alert DROP COLUMN IF EXISTS peak_hour;

COMMENT ON COLUMN energy_alert.peak_interval_start IS 'UTC start of the slot whose total_c_kwh triggered the alert.';
COMMENT ON COLUMN energy_alert.price_date          IS 'Calendar day the alert is about (kept for human-friendly summaries).';

COMMIT;
