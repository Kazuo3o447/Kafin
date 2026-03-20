import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    proxyTimeout: 300000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://kafin-backend:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
