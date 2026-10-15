import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: { proxyTimeout: 125000 },
  async rewrites() {
    // El navegador solo habla con localhost:3000; FastAPI escucha en localhost:8000.
    return [{ source: "/api/quibar/:path*", destination: "http://127.0.0.1:8000/api/quibar/:path*" }];
  },
};

export default nextConfig;
