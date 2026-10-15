import type { NextConfig } from "next";

const apiHost = process.env.QUIBAR_API_HOST ?? "127.0.0.1";
const apiPort = process.env.QUIBAR_API_PORT ?? "8000";

const nextConfig: NextConfig = {
  experimental: { proxyTimeout: 125000 },
  async rewrites() {
    return [{
      source: "/api/quibar/:path*",
      destination: `http://${apiHost}:${apiPort}/api/quibar/:path*`,
    }];
  },
};

export default nextConfig;
