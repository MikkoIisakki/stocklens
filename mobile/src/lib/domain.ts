import Constants from "expo-constants";

/**
 * Runtime accessor for the build-time-injected domain config.
 *
 * The actual loading from `config/domains/<name>.yaml` happens in
 * `app.config.ts` (Node.js, build time). At runtime we just read the
 * already-parsed object out of `Constants.expoConfig.extra`.
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
  default_region: string;
}

interface ExtraConfig {
  domain: DomainConfig;
  apiBaseUrl: string;
  apiKey: string;
}

function readExtra(): ExtraConfig {
  const extra = Constants.expoConfig?.extra as ExtraConfig | undefined;
  if (!extra?.domain) {
    throw new Error(
      "Constants.expoConfig.extra.domain is missing — did app.config.ts run?",
    );
  }
  return extra;
}

export function getDomainConfig(): DomainConfig {
  return readExtra().domain;
}

export function getApiBaseUrl(): string {
  return readExtra().apiBaseUrl.replace(/\/+$/, "");
}

export function getApiKey(): string {
  return readExtra().apiKey;
}
