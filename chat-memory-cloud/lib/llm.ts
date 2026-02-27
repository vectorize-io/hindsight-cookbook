import OpenAI from 'openai';
import Groq from 'groq-sdk';

const provider = (process.env.LLM_PROVIDER || 'openai').toLowerCase();

function getClient() {
  if (provider === 'groq') {
    if (!process.env.GROQ_API_KEY) {
      throw new Error('GROQ_API_KEY environment variable is not set');
    }
    return { client: new Groq({ apiKey: process.env.GROQ_API_KEY }), model: process.env.LLM_MODEL || 'qwen/qwen3-32b' };
  }
  if (!process.env.OPENAI_API_KEY) {
    throw new Error('OPENAI_API_KEY environment variable is not set');
  }
  return { client: new OpenAI({ apiKey: process.env.OPENAI_API_KEY }), model: process.env.LLM_MODEL || 'gpt-4o' };
}

export async function generateChatResponse(
  userMessage: string,
  memories: string = '',
  userId: string
): Promise<string> {
  const { client, model } = getClient();

  const systemPrompt = `You are a helpful AI assistant with memory. You remember past conversations and user preferences.

${memories ? `Here's what you remember about this user:\n${memories}\n` : 'No previous memories found for this user yet.'}

Be conversational, helpful, and reference relevant memories when appropriate. If this is the first conversation or no memories are available, introduce yourself and ask the user about themselves to start building memories.`;

  const completion = await client.chat.completions.create({
    messages: [
      {
        role: 'system' as const,
        content: systemPrompt + (provider === 'groq' ? '\n\nPlease respond directly without showing any reasoning or thinking process.' : ''),
      },
      {
        role: 'user' as const,
        content: userMessage,
      },
    ],
    model,
    temperature: 0.8,
    max_tokens: 4096,
  });

  let response = completion.choices[0]?.message?.content || 'I apologize, but I was unable to generate a response.';

  // Clean up think tags from models that use them (e.g. Qwen on Groq)
  if (provider === 'groq') {
    response = response.replace(/<think\s*\/?>[\s\S]*?<\/think>/gi, '');
  }

  return response.trim();
}
