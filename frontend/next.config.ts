import type { NextConfig } from "next";

const internalApiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 60000,   // 60s — reicht für alle Endpoints
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${internalApiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
