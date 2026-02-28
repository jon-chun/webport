/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "www.helixcenter.org",
      },
      {
        protocol: "https",
        hostname: "media.helixcenter.org",
      },
      {
        protocol: "https",
        hostname: "secure.gravatar.com",
      },
    ],
  },
};

module.exports = nextConfig;
