import Groq from 'groq-sdk';

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY!,
});

export async function generateChatResponse(
  userMessage: string,
  memories: string = '',
  userId: string
): Promise<string> {
  if (!process.env.GROQ_API_KEY) {
    throw new Error('GROQ_API_KEY environment variable is not set');
  }
  const systemPrompt = `You are a helpful AI assistant with memory. You remember past conversations and user preferences.

${memories ? `Here's what you remember about this user:\n${memories}\n` : 'No previous memories found for this user yet.'}

Be conversational, helpful, and reference relevant memories when appropriate. If this is the first conversation or no memories are available, introduce yourself and ask the user about themselves to start building memories.`;

  const completion = await groq.chat.completions.create({
    messages: [
      {
        role: 'system',
        content: systemPrompt + "\n\nPlease respond directly without showing any reasoning or thinking process.",
      },
      {
        role: 'user',
        content: userMessage,
      },
    ],
    model: 'qwen/qwen3-32b',
    temperature: 0.8,
    top_p: 0.8,
    max_tokens: 4096,
  });

  let response = completion.choices[0]?.message?.content || 'I apologize, but I was unable to generate a response.';

  // Remove empty think tags and clean up response
  response = response.replace(/<think\s*\/?>[\s\S]*?<\/think>/gi, '');
  response = response.replace(/<think[\s\S]*?<\/think>/gi, '');
  response = response.trim();

  return response;
}