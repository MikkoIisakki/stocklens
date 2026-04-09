-- Seed: 002_energy_regions
-- Description: Nordpool bidding zones with VAT and electricity tax parameters
-- Finland is the primary target region; Baltics and Sweden included for future use.

BEGIN;

INSERT INTO energy_region (code, name, country, vat_rate, electricity_tax_c_kwh) VALUES
-- Finland: VAT 25.5% (from Sep 2024), electricity tax Category I 2.24 c/kWh
('FI',  'Finland',      'FI', 0.2550, 2.2400),
-- Sweden: VAT 25%, no electricity excise tax (energy tax collected differently)
('SE3', 'Sweden North', 'SE', 0.2500, 0.0000),
('SE4', 'Sweden South', 'SE', 0.2500, 0.0000),
-- Baltics: own VAT rates, no electricity excise tax in Nordpool day-ahead context
('EE',  'Estonia',      'EE', 0.2200, 0.0000),
('LV',  'Latvia',       'LV', 0.2100, 0.0000),
('LT',  'Lithuania',    'LT', 0.2100, 0.0000)
ON CONFLICT (code) DO NOTHING;

COMMIT;
