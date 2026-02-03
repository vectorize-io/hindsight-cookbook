import { NextRequest, NextResponse } from 'next/server';
import { query, queryOne } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    // Use SELECT * to avoid column name caching issues
    const sessions = await query(
      `SELECT * FROM tracking_sessions ORDER BY created_at DESC`
    );

    return NextResponse.json({ sessions });
  } catch (error: any) {
    console.error('Error fetching sessions:', error);
    return NextResponse.json(
      { error: 'Failed to fetch sessions' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      name,
      country,
      state,
      city,
      topic,
      candidates,
      timespanStart,
      timespanEnd,
      frequency,
      scrapingMode,
    } = body;

    if (!name || !country || !topic || !candidates || !timespanStart || !timespanEnd || !frequency) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    const session = await queryOne(
      `INSERT INTO tracking_sessions
       (name, country, state, city, topic, candidates, timespan_start, timespan_end, frequency, scraping_mode)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       RETURNING *`,
      [name, country, state, city, topic, candidates, new Date(timespanStart), new Date(timespanEnd), frequency, scrapingMode || 'direct_web']
    );

    return NextResponse.json({ session }, { status: 201 });
  } catch (error) {
    console.error('Error creating session:', error);
    return NextResponse.json(
      { error: 'Failed to create session' },
      { status: 500 }
    );
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      id,
      name,
      country,
      state,
      city,
      topic,
      candidates,
      timespanStart,
      timespanEnd,
      frequency,
      scrapingMode,
    } = body;

    if (!id) {
      console.error('PATCH /api/sessions - Missing session ID');
      return NextResponse.json(
        { error: 'Session ID is required' },
        { status: 400 }
      );
    }

    // Validate date fields
    if (!timespanStart || !timespanEnd) {
      console.error('PATCH /api/sessions - Missing timespan fields:', { timespanStart, timespanEnd });
      return NextResponse.json(
        { error: 'Timespan start and end are required' },
        { status: 400 }
      );
    }

    const session = await queryOne(
      `UPDATE tracking_sessions
       SET name = $1,
           country = $2,
           state = $3,
           city = $4,
           topic = $5,
           candidates = $6,
           timespan_start = $7,
           timespan_end = $8,
           frequency = $9,
           scraping_mode = $10,
           updated_at = NOW()
       WHERE id = $11
       RETURNING *`,
      [
        name,
        country,
        state,
        city,
        topic,
        candidates,
        new Date(timespanStart),
        new Date(timespanEnd),
        frequency,
        scrapingMode || 'direct_web',
        id,
      ]
    );

    if (!session) {
      console.error('PATCH /api/sessions - Session not found:', id);
      return NextResponse.json(
        { error: 'Session not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({ session });
  } catch (error: any) {
    console.error('Error updating session:', error);
    console.error('Error details:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
    return NextResponse.json(
      { error: 'Failed to update session', details: error.message },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');

    if (!id) {
      return NextResponse.json(
        { error: 'Session ID is required' },
        { status: 400 }
      );
    }

    await query(
      `DELETE FROM tracking_sessions WHERE id = $1`,
      [id]
    );

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting session:', error);
    return NextResponse.json(
      { error: 'Failed to delete session' },
      { status: 500 }
    );
  }
}
