/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The API is a separate service. Proxying through /api keeps the browser on
  // one origin, which avoids CORS entirely in development and means the
  // deployed build only needs one hostname.
  async rewrites() {
    const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8001";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default nextConfig;
