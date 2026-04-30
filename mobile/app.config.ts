import type { ExpoConfig } from "expo/config";
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

/**
 * Build-time Expo config. Reads `config/domains/<name>.yaml` from the repo
 * root and injects the parsed object into Constants.expoConfig.extra so
 * runtime code can read branding and region metadata without bundling
 * the YAML loader. Mirrors the web shell's `web/src/lib/domain.ts` (ADR-008).
 *
 * Selecting which domain to build:
 *   PULSE_DOMAIN=energy npx expo start
 *
 * See ADR-009 for the full rationale and the API-key trade-off.
 */

interface RegionConfig {
  code: string;
  name: string;
  country: string;
}

interface DomainConfig {
  name: string;
  display_name: string;
  description: string;
  regions: RegionConfig[];
  default_region: string;
}

const REPO_ROOT = path.resolve(__dirname, "..");

function loadDomainConfig(): DomainConfig {
  const name = process.env.PULSE_DOMAIN;
  if (!name) {
    throw new Error(
      "PULSE_DOMAIN env var is not set. Pick a name under config/domains/<name>.yaml.",
    );
  }
  const file = path.join(REPO_ROOT, "config", "domains", `${name}.yaml`);
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
  return {
    name: String(data.name ?? name),
    display_name: String(data.display_name ?? name),
    description: typeof data.description === "string" ? data.description : "",
    regions,
    default_region: regions[0].code,
  };
}

export default (): ExpoConfig => {
  const domain = loadDomainConfig();
  return {
    name: domain.display_name,
    slug: `pulse-${domain.name}`,
    version: "0.1.0",
    extra: {
      domain,
      // API URL + key are read from EXPO_PUBLIC_* so EAS build profiles can
      // override them per environment. The "PUBLIC" prefix is honest: these
      // values WILL be in the JS bundle. See ADR-009 for the migration path
      // to per-install device-registered keys.
      apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
      apiKey: process.env.EXPO_PUBLIC_API_KEY ?? "",
    },
  };
};
