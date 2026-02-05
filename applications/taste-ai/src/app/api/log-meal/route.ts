// @ts-nocheck - TypeScript has issues resolving tool types from local package
import { generateText } from 'ai';
import { hindsightTools, llmModel, getAppDocument, saveAppDocument, addMealToDocument, BANK_ID, getMentalModelId } from '@/lib/hindsight';

// Ensure the goals mental model exists (one per user, tagged with user:username)
async function ensureGoalsMentalModel(username: string): Promise<void> {
  // Calculate deterministic mental model ID
  const mentalModelId = getMentalModelId(username, 'goals');

  // Try to get the existing mental model
  try {
    // @ts-ignore - TS can't resolve mental model tools from local package
    const existing = await hindsightTools.queryMentalModel.execute({
      bankId: BANK_ID,
      mentalModelId: mentalModelId,
    });

    if (existing) {
      console.log('[TasteAI] Using existing goals mental model:', mentalModelId);
      return;
    }
  } catch (e) {
    // Mental model doesn't exist yet, create it below
  }

  // Create a new mental model for this user with the calculated ID
  try {
    // @ts-ignore - TS can't resolve mental model tools from local package
    const result = (await hindsightTools.createMentalModel.execute({
      bankId: BANK_ID,
      mentalModelId: mentalModelId, // Pass the calculated ID
      name: `${username}'s Goal Progress`,
      sourceQuery: `Analyze ${username}'s dietary goals and eating patterns. In exactly 2 sentences, describe their progress towards their stated goals (weight loss, muscle gain, healthy eating, etc.). Be specific, encouraging, and factual based on their recent meals.`,
      maxTokens: 512,
      tags: [`user:${username}`], // Tag with user for filtering
      autoRefresh: true, // Auto-refresh after new consolidations
    })) as { mentalModelId: string; createdAt: string };

    console.log('[TasteAI] Created goals mental model:', result.mentalModelId, 'for', username);
  } catch (e) {
    console.error('[TasteAI] Failed to create goals mental model:', e);
    throw e;
  }
}

export async function POST(req: Request) {
  const { username, food, action, mealType } = await req.json();

  if (!username) {
    return Response.json({ error: 'Username required' }, { status: 400 });
  }

  try {
    const today = new Date();
    const mealDate = today.toISOString().split('T')[0];

    // Handle all actions - store meals in document only
    switch (action) {
      case 'ate_today':
      case 'ate_yesterday': {
        // Just a note - we don't store "already ate" in document
        return Response.json({ success: true });
      }

      case 'never': {
        // Store dislike in preferences
        const doc = await getAppDocument(username);
        const currentDislikes = doc.preferences.dislikes || [];
        if (!currentDislikes.includes(food.name)) {
          doc.preferences.dislikes = [...currentDislikes, food.name];
          await saveAppDocument(doc);
        }
        return Response.json({ success: true });
      }

      case 'cook': {
        // Store meal in document
        const storedMeal = await addMealToDocument(username, {
          name: food.name,
          emoji: food.emoji || '🍽️',
          description: food.description,
          type: mealType,
          date: mealDate,
          healthScore: food.healthScore,
          timeMinutes: food.timeMinutes,
          ingredients: food.ingredients,
          instructions: food.instructions,
          tags: food.tags,
          action: 'cooked',
        });

        console.log(`[TasteAI] Stored meal in document for ${username}: "${storedMeal.name}"`);

        // Ensure mental model exists (will auto-refresh after consolidation)
        await ensureGoalsMentalModel(username);

        return Response.json({ success: true, meal: storedMeal });
      }

      default:
        return Response.json({ error: 'Invalid action' }, { status: 400 });
    }
  } catch (error) {
    console.error('Log meal error:', error);
    return Response.json({ error: 'Failed to log meal' }, { status: 500 });
  }
}
