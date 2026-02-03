import { NextRequest, NextResponse } from 'next/server';
import { generateChatResponse } from '@/lib/groq';
import { createUserBank, storeConversation, getRelevantMemories } from '@/lib/hindsight';

export async function POST(request: NextRequest) {
  try {
    const startTime = Date.now();
    const { message, userId } = await request.json();

    if (!message || !userId) {
      return NextResponse.json(
        { error: 'Message and userId are required' },
        { status: 400 }
      );
    }

    console.log('🚀 Starting chat request for user:', userId);

    // Ensure user has a memory bank
    const bankStart = Date.now();
    await createUserBank(userId);
    console.log('🏦 Bank creation took:', Date.now() - bankStart, 'ms');

    // Get relevant memories for context
    const memoryStart = Date.now();
    const memories = await getRelevantMemories(userId, message);
    console.log('🧠 Memory retrieval took:', Date.now() - memoryStart, 'ms');

    // Generate response using Groq
    const groqStart = Date.now();
    const response = await generateChatResponse(message, memories, userId);
    console.log('🤖 Groq response took:', Date.now() - groqStart, 'ms');

    // Store the conversation in Hindsight (don't wait for this)
    storeConversation(userId, message, response).catch(error => {
      console.error('Error storing conversation:', error);
    });

    console.log('⚡ Total request took:', Date.now() - startTime, 'ms');
    return NextResponse.json({ response });
  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { error: 'Failed to generate response' },
      { status: 500 }
    );
  }
}