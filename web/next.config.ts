import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Keep small container builds from spawning a worker for every host CPU.
  experimental: { cpus: 2 },
};
export default config;
