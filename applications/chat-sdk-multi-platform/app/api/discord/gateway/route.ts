import { after } from 'next/server';
import { bot } from '@/lib/bot';

export const maxDuration = 800;

export async function GET(request: Request): Promise<Response> {
  const cronSecret = process.env.CRON_SECRET;

  // In local dev, allow unauthenticated access if no CRON_SECRET is set
  if (cronSecret) {
    const authHeader = request.headers.get('authorization');
    if (authHeader !== `Bearer ${cronSecret}`) {
      return new Response('Unauthorized', { status: 401 });
    }
  }

  if (!process.env.DISCORD_BOT_TOKEN) {
    return new Response('Discord not configured (missing DISCORD_BOT_TOKEN)', { status: 404 });
  }

  await bot.initialize();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const discord = (bot as any).getAdapter('discord');

  const durationMs = 10 * 60 * 1000; // 10 minutes
  const baseUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : 'http://localhost:3000';
  const webhookUrl = `${baseUrl}/api/webhooks/discord`;

  return discord.startGatewayListener(
    { waitUntil: (task: Promise<unknown>) => after(() => task) },
    durationMs,
    undefined,
    webhookUrl
  );
}
