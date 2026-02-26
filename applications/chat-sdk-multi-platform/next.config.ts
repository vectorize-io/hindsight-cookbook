import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  serverExternalPackages: ['discord.js', '@discordjs/ws', 'zlib-sync'],
};

export default nextConfig;
