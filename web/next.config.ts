import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // The web shell reads config/domains/<name>.yaml from the repo root at
  // build/runtime. Next traces files imported from server code, but the
  // YAML is read with fs at runtime — declare it as an output trace asset
  // so it ships with the build.
  outputFileTracingIncludes: {
    "/**/*": ["../config/domains/*.yaml"],
  },
};

export default config;
