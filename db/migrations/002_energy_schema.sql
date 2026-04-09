-- Migration: 002_energy_schema
-- Description: Electricity domain — region config, hourly spot prices, extend ingest_run
-- Applies to: all environments

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- energy_region — Nordpool bidding zone config (VAT, electricity tax per country)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS energy_region (
    code                   TEXT         PRIMARY KEY,   -- FI | SE3 | SE4 | EE | LV | LT
    name                   TEXT         NOT NULL,
    country                TEXT         NOT NULL,      -- ISO 3166-1 alpha-2
    vat_rate               NUMERIC(5,4) NOT NULL,      -- e.g. 0.255 = 25.5%
    electricity_tax_c_kwh  NUMERIC(8,4) NOT NULL,      -- government excise tax c/kWh, 0 if not applicable
    active                 BOOLEAN      NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE  energy_region                        IS 'Nordpool bidding zones with country-specific tax/VAT parameters.';
COMMENT ON COLUMN energy_region.code                   IS 'Nordpool bidding zone code, e.g. FI, SE3, SE4.';
COMMENT ON COLUMN energy_region.vat_rate               IS 'Decimal fraction, e.g. 0.255 for Finnish 25.5% VAT.';
COMMENT ON COLUMN energy_region.electricity_tax_c_kwh  IS 'Government electricity excise tax in c/kWh. Finland: 2.24. Sweden/Baltics: 0.';


-- ─────────────────────────────────────────────────────────────────────────────
-- energy_price — hourly day-ahead spot prices from Nordpool
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS energy_price (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_code     TEXT           NOT NULL REFERENCES energy_region(code),
    ingest_run_id   BIGINT         REFERENCES ingest_run(id) ON DELETE SET NULL,
    price_date      DATE           NOT NULL,
    hour            SMALLINT       NOT NULL,            -- 0–23 (local time of delivery)
    price_eur_mwh   NUMERIC(10,4)  NOT NULL,            -- raw Nordpool day-ahead price; can be negative
    spot_c_kwh      NUMERIC(8,4)   NOT NULL,            -- price_eur_mwh / 10 (excl. tax + VAT)
    total_c_kwh     NUMERIC(8,4)   NOT NULL,            -- (price_eur_mwh/10 + electricity_tax) * (1+vat_rate)
    fetched_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT energy_price_region_date_hour_uq UNIQUE (region_code, price_date, hour),
    CONSTRAINT energy_price_hour_check          CHECK (hour BETWEEN 0 AND 23),
    CONSTRAINT energy_price_eur_mwh_range       CHECK (price_eur_mwh >= -4000)  -- Nordpool floor is –4000 EUR/MWh
);

CREATE INDEX IF NOT EXISTS energy_price_region_date_idx
    ON energy_price (region_code, price_date DESC, hour);

COMMENT ON TABLE  energy_price               IS 'Hourly day-ahead electricity spot prices per Nordpool bidding zone.';
COMMENT ON COLUMN energy_price.price_eur_mwh IS 'Raw Nordpool day-ahead price in EUR/MWh. Negative values are valid.';
COMMENT ON COLUMN energy_price.spot_c_kwh    IS 'Spot price converted to c/kWh (÷10). Does not include tax or VAT.';
COMMENT ON COLUMN energy_price.total_c_kwh   IS 'Consumer-relevant price: (spot + electricity tax) × (1 + VAT). Excludes distribution fee and retailer margin.';
COMMENT ON COLUMN energy_price.hour          IS 'Hour of delivery in local time (0 = 00:00–01:00). Day-ahead prices cover the next calendar day.';


-- ─────────────────────────────────────────────────────────────────────────────
-- Extend ingest_run.market to accept ENERGY domain
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE ingest_run DROP CONSTRAINT ingest_run_market_check;
ALTER TABLE ingest_run ADD CONSTRAINT ingest_run_market_check
    CHECK (market IN ('US', 'FI', 'ALL', 'ENERGY'));

COMMIT;
