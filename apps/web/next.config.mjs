/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone bundles only what the server imports, so the production image
  // does not have to carry node_modules.
  output: "standalone",
  // A production build and `next dev` both write .next by default, so running
  // one while the other is serving leaves the dev server with a half-replaced
  // build and MODULE_NOT_FOUND on every request. Verification builds set
  // NEXT_DIST_DIR and stay out of its way.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // The API is a separate service. Proxying through /api keeps the browser on
  // one origin, which avoids CORS entirely in development and means the
  // deployed build only needs one hostname.
  async rewrites() {
    const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8001";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default nextConfig;
