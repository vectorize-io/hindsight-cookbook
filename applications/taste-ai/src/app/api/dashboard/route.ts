// @ts-nocheck - TypeScript has issues resolving tool types from local package
import { getAppDocument, hindsightTools, BANK_ID, getMentalModelId } from '@/lib/hindsight';

export async function GET(req: Request) {
  try {
    // Get username from query params
    const { searchParams } = new URL(req.url);
    const username = searchParams.get('username');

    if (!username) {
      return Response.json({ error: 'Username required' }, { status: 400 });
    }

    // Get app document for this user
    const appDoc = await getAppDocument(username);

    // Get meals from document (last 10)
    const meals = appDoc.meals.slice(0, 10);

    // Query mental model fresh for goal progress and suggestions (calculate ID instead of storing it)
    let goalProgress: any = null;
    if (meals.length > 0) {
      try {
        const mentalModelId = getMentalModelId(username, 'goals');
        // @ts-ignore - TS can't resolve mental model tools from local package
        const mentalModelResult = await hindsightTools.queryMentalModel.execute({
          bankId: BANK_ID,
          mentalModelId: mentalModelId,
        });

        if (mentalModelResult?.content) {
          goalProgress = {
            insight: mentalModelResult.content, // Fresh goal progress and suggestions
          };
        }
      } catch (e) {
        console.log('[Dashboard] Failed to query mental model:', e);
      }
    }

    // Include preferences for display and onboarding check
    const preferences = appDoc.preferences || {};

    console.log(`[Dashboard] Loaded ${meals.length} meals for ${username}, goalProgress: ${goalProgress ? 'fresh from mental model' : 'none'}`);

    return Response.json({ goalProgress, meals, preferences });
  } catch (error) {
    console.error('Dashboard error:', error);
    return Response.json({ health: null, meals: [], preferences: {} });
  }
}
