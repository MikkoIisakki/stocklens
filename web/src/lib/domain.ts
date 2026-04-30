import "server-only";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

/**
 * Server-only loader for `config/domains/<name>.yaml`.
 *
 * Mirrors the backend's app.common.domain (ADR-006). This module narrows
 * the schema to just the fields the web shell needs — branding and the
 * default region. Adding a new field requires updating both the Python
 * model and this file in the same PR.
 */

export interface RegionConfig {
  code: string;
  name: string;
  country: string;
}

export interface DomainConfig {
  name: string;
  display_name: string;
  description: string;
  regions: RegionConfig[];
  /** First region in the list is the default landing-page region. */
  default_region: string;
}

let _cached: DomainConfig | null = null;

const REPO_ROOT = path.resolve(process.cwd(), "..");
const CONFIG_DIR = path.join(REPO_ROOT, "config", "domains");

function envDomain(): string {
  const name = process.env.PULSE_DOMAIN;
  if (!name) {
    throw new Error(
      "PULSE_DOMAIN env var is not set. Set it to a name under config/domains/<name>.yaml.",
    );
  }
  return name;
}

export function loadDomainConfig(): DomainConfig {
  if (_cached) return _cached;

  const name = envDomain();
  const file = path.join(CONFIG_DIR, `${name}.yaml`);
  if (!fs.existsSync(file)) {
    throw new Error(`Domain config not found: ${file}`);
  }
  const raw = yaml.load(fs.readFileSync(file, "utf-8"));
  if (raw === null || typeof raw !== "object") {
    throw new Error(`${file}: top-level must be a mapping`);
  }
  const data = raw as Record<string, unknown>;

  const regions = Array.isArray(data.regions)
    ? (data.regions as Record<string, unknown>[]).map((r) => ({
        code: String(r.code),
        name: String(r.name),
        country: String(r.country),
      }))
    : [];

  if (regions.length === 0) {
    throw new Error(`${file}: 'regions' must be a non-empty list`);
  }

  _cached = {
    name: String(data.name ?? name),
    display_name: String(data.display_name ?? name),
    description: typeof data.description === "string" ? data.description : "",
    regions,
    default_region: regions[0].code,
  };
  return _cached;
}
