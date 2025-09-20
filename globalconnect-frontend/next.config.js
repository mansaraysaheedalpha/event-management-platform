/** @type {import('next').NextConfig} */
const nextConfig = {
  // Your Next.js configuration options will go here in the future.
   // ✅ THE FIX: This section tells Next.js to trust images from placehold.co
   images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "placehold.co",
        port: "",
        pathname: "/**",
      },
      // ✅ ADD THIS NEW BLOCK
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        port: "",
        pathname: "/**",
      },
    ],
  },
};

module.exports = nextConfig;