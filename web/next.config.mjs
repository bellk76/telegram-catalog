const apiInternalUrl = (process.env.API_INTERNAL_URL?.trim() || "http://localhost:8000").replace(
  /\/+$/,
  "",
);
const botInternalUrl = (process.env.BOT_INTERNAL_URL?.trim() || "http://bot:8080").replace(
  /\/+$/,
  "",
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiInternalUrl}/api/:path*`,
      },
      {
        source: "/telegram/:path*",
        destination: `${botInternalUrl}/telegram/:path*`,
      },
    ];
  },
};

export default nextConfig;
