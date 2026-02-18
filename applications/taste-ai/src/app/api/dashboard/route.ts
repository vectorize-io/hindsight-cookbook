import { getAppDocument, hindsightClient, BANK_ID, getMentalModelId } from '@/lib/hindsight';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const username = searchParams.get('username');

    if (!username) {
      return Response.json({ error: 'Username required' }, { status: 400 });
    }

    const appDoc = await getAppDocument(username);
    const meals = appDoc.meals.slice(0, 10);

    let goalProgress: { insight: string } | null = null;
    if (meals.length > 0) {
      try {
        const mentalModelId = getMentalModelId(username, 'goals');
        const mentalModelResult = await hindsightClient.getMentalModel(BANK_ID, mentalModelId);

        if (mentalModelResult?.content) {
          goalProgress = {
            insight: mentalModelResult.content,
          };
        }
      } catch (e) {
        console.log('[Dashboard] Failed to query mental model:', e);
      }
    }

    const preferences = appDoc.preferences || {};

    console.log(`[Dashboard] Loaded ${meals.length} meals for ${username}, goalProgress: ${goalProgress ? 'fresh from mental model' : 'none'}`);

    return Response.json({ goalProgress, meals, preferences });
  } catch (error) {
    console.error('Dashboard error:', error);
    return Response.json({ health: null, meals: [], preferences: {} });
  }
}
