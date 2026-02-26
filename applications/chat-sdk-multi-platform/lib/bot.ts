import { Chat } from 'chat';
import { createSlackAdapter } from '@chat-adapter/slack';
import { createDiscordAdapter } from '@chat-adapter/discord';
import { createMemoryState } from '@chat-adapter/state-memory';
import { withHindsightChat } from '@vectorize-io/hindsight-chat';
import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';
import { hindsight } from './hindsight';

const BANK_ID = process.env.HINDSIGHT_BANK_ID ?? 'hindsight-demo';

const slack = createSlackAdapter();
const discord = process.env.DISCORD_BOT_TOKEN ? createDiscordAdapter() : null;

const adapters = discord
  ? { slack, discord }
  : { slack };

export const bot = new Chat({
  userName: 'memory-bot',
  adapters,
  state: createMemoryState(),
});

// Ensure the memory bank exists on startup
hindsight.createBank(BANK_ID, {}).catch(() => {
  // Bank may already exist, that's fine
});

// --- @mention handler: recall memories, respond with LLM ---
bot.onNewMention(
  withHindsightChat(
    {
      client: hindsight,
      bankId: () => BANK_ID,
      retain: { enabled: true, tags: ['chat'] },
    },
    async (thread, message, ctx) => {
      await thread.subscribe();

      const systemPrompt = ctx.memoriesAsSystemPrompt();
      const system = [
        'You are a helpful assistant with long-term memory powered by Hindsight.',
        'You remember things users have told you across conversations and platforms (Slack, Discord, etc.).',
        'Keep responses concise and conversational.',
        systemPrompt
          ? `\nHere is what you remember about this user:\n${systemPrompt}`
          : '\nYou have no memories about this user yet.',
      ].join('\n');

      const { text } = await generateText({
        model: openai('gpt-4o-mini'),
        system,
        prompt: message.text,
      });

      await thread.post(text);

      await ctx.retain(
        `User: ${message.text}\nAssistant: ${text}`
      );
    }
  )
);

// --- Subscribed thread handler: retain follow-ups, respond with LLM ---
bot.onSubscribedMessage(
  withHindsightChat(
    {
      client: hindsight,
      bankId: () => BANK_ID,
    },
    async (thread, message, ctx) => {
      const systemPrompt = ctx.memoriesAsSystemPrompt();
      const system = [
        'You are a helpful assistant with long-term memory powered by Hindsight.',
        'You remember things users have told you across conversations and platforms (Slack, Discord, etc.).',
        'Keep responses concise and conversational.',
        'This is a follow-up message in an ongoing thread.',
        systemPrompt
          ? `\nHere is what you remember about this user:\n${systemPrompt}`
          : '',
      ].join('\n');

      const { text } = await generateText({
        model: openai('gpt-4o-mini'),
        system,
        prompt: message.text,
      });

      await thread.post(text);

      await ctx.retain(
        `User (follow-up): ${message.text}\nAssistant: ${text}`
      );
    }
  )
);
