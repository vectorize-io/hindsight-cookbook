import { NextRequest, NextResponse } from 'next/server';
import { query } from '@/lib/db';
import { StancePipeline } from '@/lib/stance-pipeline';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, candidate, topic, location, timeRange } = body;

    if (!sessionId || !candidate || !topic) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Convert timeRange strings to Date objects if provided
    const parsedTimeRange = timeRange
      ? {
          start: new Date(timeRange.start),
          end: new Date(timeRange.end),
        }
      : undefined;

    // Initialize pipeline
    const pipeline = new StancePipeline(sessionId);

    // Process candidate
    const stances = await pipeline.processCandidate(
      candidate,
      topic,
      parsedTimeRange
    );

    return NextResponse.json({ stances });
  } catch (error) {
    console.error('Error processing stance:', error);
    return NextResponse.json(
      { error: 'Failed to process stance' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const sessionId = searchParams.get('sessionId');
    const candidate = searchParams.get('candidate');

    if (!sessionId) {
      return NextResponse.json(
        { error: 'sessionId is required' },
        { status: 400 }
      );
    }

    let queryStr = `
      SELECT sp.*,
             json_agg(
               json_build_object(
                 'id', r.id,
                 'url', r.url,
                 'title', r.title,
                 'excerpt', r.excerpt,
                 'published_date', r.published_date,
                 'source_type', r.source_type
               )
             ) as sources
      FROM stance_points sp
      LEFT JOIN stance_point_references spr ON sp.id = spr.stance_point_id
      LEFT JOIN "references" r ON spr.reference_id = r.id
      WHERE sp.session_id = $1
    `;

    const params: any[] = [sessionId];

    if (candidate) {
      queryStr += ' AND sp.candidate = $2';
      params.push(candidate);
    }

    queryStr += ' GROUP BY sp.id ORDER BY sp.timestamp ASC';

    const stances = await query(queryStr, params);

    return NextResponse.json({ stances });
  } catch (error) {
    console.error('Error fetching stances:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stances' },
      { status: 500 }
    );
  }
}
