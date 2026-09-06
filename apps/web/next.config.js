/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // A second Next process (E2E on :3100, `next build` while `next dev` runs) must never share .next — it corrupts the dev server.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010" },
};
module.exports = nextConfig;
