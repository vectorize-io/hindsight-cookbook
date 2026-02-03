import { HindsightClient } from '@vectorize-io/hindsight-client';

const hindsightClient = new HindsightClient({
  baseUrl: process.env.HINDSIGHT_API_URL || 'http://localhost:8888',
});

export async function createUserBank(userId: string) {
  try {
    await hindsightClient.createBank(userId, {
      name: `Chat Memory for ${userId}`,
      background: "This is a conversational AI assistant that remembers user preferences, past conversations, and personal details shared during our interactions.",
      disposition: {
        empathy: 4,
        skepticism: 2,
        literalism: 3,
      }
    });
  } catch (error: any) {
    console.error('Error creating bank:', error);
    // Bank might already exist, or Hindsight server might be starting up
    // Don't throw - let the app continue without memory temporarily
  }
}

export async function storeConversation(userId: string, userMessage: string, assistantMessage: string) {
  try {
    const conversation = `User: ${userMessage}\nAssistant: ${assistantMessage}`;

    await hindsightClient.retain(userId, conversation, {
      context: 'conversation',
      metadata: { timestamp: new Date().toISOString() }
    });
  } catch (error) {
    console.error('Error storing conversation:', error);
    // Don't throw - let the conversation continue even if storage fails
  }
}

export async function getRelevantMemories(userId: string, query: string) {
  try {
    const response = await hindsightClient.recall(userId, query, {
      maxTokens: 4096,
      budget: 'mid'
    });

    if (!response || !response.results) {
      console.warn('Hindsight API returned empty response - server may be starting up');
      return '';
    }

    return response.results.map(memory => memory.text).join('\n');
  } catch (error) {
    console.error('Error retrieving memories:', error);
    return '';
  }
}