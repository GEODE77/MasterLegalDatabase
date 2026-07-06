/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  outputFileTracingExcludes: {
    "*": [
      "./data/**/*",
      "./.next/**/*",
      "./.next-build/**/*"
    ]
  }
};

export default nextConfig;
