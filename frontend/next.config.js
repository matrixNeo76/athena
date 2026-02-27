/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  /**
   * Standalone output — bundles only the files needed for production.
   * Results in a much smaller Docker image (copies only required node_modules).
   * See: https://nextjs.org/docs/pages/api-reference/next-config-js/output
   */
  output: 'standalone',

  /**
   * API & WebSocket rewrites.
   *
   * In local dev, NEXT_PUBLIC_API_URL is http://localhost:8000 (set in .env.local).
   * In production, set it to your deployed backend URL so requests are proxied
   * correctly through the Next.js server instead of hitting the origin directly.
   *
   * NOTE: Next.js rewrites proxy HTTP, but NOT raw WebSocket connections.
   * The frontend's buildWsUrl() constructs the WS URL directly from
   * NEXT_PUBLIC_API_URL, which already handles this case.
   */
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
