import { NextRequest, NextResponse } from 'next/server';
import { scheduler } from '@/lib/scheduler';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { action, sessionId, frequency } = body;

    switch (action) {
      case 'start':
        if (!sessionId || !frequency) {
          return NextResponse.json(
            { error: 'Missing required fields' },
            { status: 400 }
          );
        }
        scheduler.scheduleSession(sessionId, frequency);
        return NextResponse.json({ message: 'Session scheduled' });

      case 'stop':
        if (!sessionId) {
          return NextResponse.json(
            { error: 'Missing sessionId' },
            { status: 400 }
          );
        }
        scheduler.stopSession(sessionId);
        return NextResponse.json({ message: 'Session stopped' });

      case 'run':
        if (!sessionId) {
          return NextResponse.json(
            { error: 'Missing sessionId' },
            { status: 400 }
          );
        }
        // Trigger immediate run (async)
        const { query } = await import('@/lib/db');
        const sessions = await query(
          'SELECT * FROM tracking_sessions WHERE id = $1',
          [sessionId]
        );
        if (sessions && sessions[0]) {
          scheduler.runSession(sessions[0]);
        }
        return NextResponse.json({ message: 'Session run triggered' });

      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('Scheduler error:', error);
    return NextResponse.json(
      { error: 'Scheduler operation failed' },
      { status: 500 }
    );
  }
}
