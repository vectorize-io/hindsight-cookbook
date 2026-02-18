import { hindsightClient, getAppDocument, saveAppDocument, addMealToDocument, BANK_ID, getMentalModelId } from '@/lib/hindsight';

// Ensure the goals mental model exists (one per user, tagged with user:username)
async function ensureGoalsMentalModel(username: string): Promise<void> {
  const mentalModelId = getMentalModelId(username, 'goals');

  try {
    const existing = await hindsightClient.getMentalModel(BANK_ID, mentalModelId);
    if (existing) {
      console.log('[TasteAI] Using existing goals mental model:', mentalModelId);
      return;
    }
  } catch (e) {
    // Mental model doesn't exist yet, create it below
  }

  try {
    const result = await hindsightClient.createMentalModel(BANK_ID, {
      id: mentalModelId,
      name: `${username}'s Goal Progress`,
      sourceQuery: `Analyze ${username}'s dietary goals and eating patterns. In exactly 2 sentences, describe their progress towards their stated goals (weight loss, muscle gain, healthy eating, etc.). Be specific, encouraging, and factual based on their recent meals.`,
      maxTokens: 512,
      tags: [`user:${username}`],
      trigger: { refresh_after_consolidation: true },
    });

    console.log('[TasteAI] Created goals mental model:', result.mental_model_id, 'for', username);
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

    switch (action) {
      case 'ate_today':
      case 'ate_yesterday': {
        return Response.json({ success: true });
      }

      case 'never': {
        const doc = await getAppDocument(username);
        const currentDislikes = doc.preferences.dislikes || [];
        if (!currentDislikes.includes(food.name)) {
          doc.preferences.dislikes = [...currentDislikes, food.name];
          await saveAppDocument(doc);
        }
        return Response.json({ success: true });
      }

      case 'cook': {
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
