import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function seed() {
  const client = await pool.connect();

  try {
    console.log('🌱 Seeding demo data...');

    // Create a demo tracking session
    const sessionResult = await client.query(`
      INSERT INTO tracking_sessions
      (country, state, city, topic, candidates, timespan_start, timespan_end, frequency, status)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING id
    `, [
      'United States',
      'California',
      'San Francisco',
      'Climate Change Policy',
      ['Senator Jane Smith', 'Governor Bob Johnson', 'Representative Alice Chen'],
      new Date('2024-06-01'),
      new Date('2024-11-23'),
      'weekly',
      'active'
    ]);

    const sessionId = sessionResult.rows[0].id;
    console.log(`✓ Created session: ${sessionId}`);

    // Helper to create references
    const createReference = async (url: string, title: string, date: Date, type: string) => {
      const result = await client.query(`
        INSERT INTO "references" (url, title, excerpt, published_date, source_type)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title
        RETURNING id
      `, [
        url,
        title,
        `Excerpt from ${title}. This is a simulated reference for demonstration purposes.`,
        date,
        type
      ]);
      return result.rows[0].id;
    };

    // Helper to create stance point
    const createStancePoint = async (
      candidate: string,
      stance: string,
      summary: string,
      confidence: number,
      timestamp: Date,
      referenceIds: string[]
    ) => {
      const result = await client.query(`
        INSERT INTO stance_points
        (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
      `, [
        sessionId,
        candidate,
        'Climate Change Policy',
        stance,
        summary,
        confidence,
        timestamp
      ]);

      const stanceId = result.rows[0].id;

      // Link references
      for (const refId of referenceIds) {
        await client.query(`
          INSERT INTO stance_point_references (stance_point_id, reference_id)
          VALUES ($1, $2)
          ON CONFLICT DO NOTHING
        `, [stanceId, refId]);
      }

      return stanceId;
    };

    // Senator Jane Smith - Evolution from cautious to strong supporter
    console.log('Creating stances for Senator Jane Smith...');

    const ref1 = await createReference(
      'https://example.com/smith-june-2024',
      'Senator Smith Discusses Energy Policy at Town Hall',
      new Date('2024-06-15'),
      'news'
    );
    await createStancePoint(
      'Senator Jane Smith',
      'Senator Smith has expressed cautious support for climate initiatives, emphasizing the need to balance environmental concerns with economic growth. She advocates for a gradual transition to renewable energy.',
      'Cautiously supportive, balanced approach',
      0.65,
      new Date('2024-06-15'),
      [ref1]
    );

    const ref2 = await createReference(
      'https://example.com/smith-july-speech',
      'Smith Delivers Climate Speech at Stanford',
      new Date('2024-07-20'),
      'speech'
    );
    await createStancePoint(
      'Senator Jane Smith',
      'In a recent speech, Senator Smith strengthened her position on climate action, calling for ambitious carbon reduction targets and increased federal investment in clean energy infrastructure.',
      'Strong support for climate action',
      0.80,
      new Date('2024-07-20'),
      [ref2]
    );

    const ref3 = await createReference(
      'https://example.com/smith-green-new-deal',
      'Senator Smith Endorses Modified Green New Deal',
      new Date('2024-09-10'),
      'press_release'
    );
    await createStancePoint(
      'Senator Jane Smith',
      'Senator Smith has endorsed a modified version of the Green New Deal, committing to aggressive climate action targets including net-zero emissions by 2040. She now advocates for rapid transition to renewable energy.',
      'Strong advocate for aggressive climate policy',
      0.90,
      new Date('2024-09-10'),
      [ref3]
    );

    // Governor Bob Johnson - Moderate to skeptical shift
    console.log('Creating stances for Governor Bob Johnson...');

    const ref4 = await createReference(
      'https://example.com/johnson-june-interview',
      'Governor Johnson Interview on State Energy Policy',
      new Date('2024-06-10'),
      'interview'
    );
    await createStancePoint(
      'Governor Bob Johnson',
      'Governor Johnson supports moderate climate policies, including state-level renewable energy incentives and emissions standards. He emphasizes practical, market-based solutions.',
      'Moderate support for climate action',
      0.70,
      new Date('2024-06-10'),
      [ref4]
    );

    const ref5 = await createReference(
      'https://example.com/johnson-energy-conference',
      'Johnson Speaks at Energy Industry Conference',
      new Date('2024-08-05'),
      'speech'
    );
    await createStancePoint(
      'Governor Bob Johnson',
      'At an energy conference, Governor Johnson expressed concerns about the pace of climate regulations, warning about potential economic impacts. He advocates for a slower, more measured approach to emissions reductions.',
      'Cautious, concerned about economic impact',
      0.55,
      new Date('2024-08-05'),
      [ref5]
    );

    const ref6 = await createReference(
      'https://example.com/johnson-delays-regulations',
      'Governor Johnson Delays New Climate Regulations',
      new Date('2024-10-15'),
      'news'
    );
    await createStancePoint(
      'Governor Bob Johnson',
      'Governor Johnson has delayed implementation of new climate regulations, citing economic concerns and the need for more industry input. He questions the feasibility of aggressive climate targets.',
      'Skeptical of aggressive climate policies',
      0.45,
      new Date('2024-10-15'),
      [ref6]
    );

    // Representative Alice Chen - Consistent strong support
    console.log('Creating stances for Representative Alice Chen...');

    const ref7 = await createReference(
      'https://example.com/chen-climate-bill',
      'Rep. Chen Introduces Comprehensive Climate Bill',
      new Date('2024-06-05'),
      'press_release'
    );
    await createStancePoint(
      'Representative Alice Chen',
      'Representative Chen has introduced comprehensive climate legislation calling for 100% clean energy by 2035, significant investment in green infrastructure, and environmental justice provisions.',
      'Strong climate action advocate',
      0.95,
      new Date('2024-06-05'),
      [ref7]
    );

    const ref8 = await createReference(
      'https://example.com/chen-climate-rally',
      'Chen Speaks at Youth Climate Rally',
      new Date('2024-07-25'),
      'speech'
    );
    await createStancePoint(
      'Representative Alice Chen',
      'At a youth climate rally, Representative Chen reaffirmed her commitment to aggressive climate action, calling the climate crisis an existential threat requiring immediate, bold action.',
      'Urgent climate action needed',
      0.92,
      new Date('2024-07-25'),
      [ref8]
    );

    const ref9 = await createReference(
      'https://example.com/chen-carbon-tax',
      'Chen Proposes Carbon Tax with Revenue Redistribution',
      new Date('2024-09-15'),
      'press_release'
    );
    await createStancePoint(
      'Representative Alice Chen',
      'Representative Chen has proposed a carbon tax with revenue redistribution to low-income communities, demonstrating continued strong commitment to climate action with emphasis on equity and justice.',
      'Climate justice champion',
      0.93,
      new Date('2024-09-15'),
      [ref9]
    );

    const ref10 = await createReference(
      'https://example.com/chen-cop-statement',
      'Rep. Chen Issues Statement on Climate Summit',
      new Date('2024-11-01'),
      'press_release'
    );
    await createStancePoint(
      'Representative Alice Chen',
      'Following the international climate summit, Representative Chen called for the U.S. to exceed its Paris Agreement commitments and lead global climate action through domestic example.',
      'Leading voice for climate action',
      0.94,
      new Date('2024-11-01'),
      [ref10]
    );

    console.log('✅ Demo data seeded successfully!');
    console.log('\nCreated:');
    console.log('- 1 tracking session');
    console.log('- 3 candidates');
    console.log('- 10 stance points');
    console.log('- 10 references');
    console.log('\nYou can now view the timeline at http://localhost:3000');

  } catch (error) {
    console.error('Error seeding data:', error);
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch(console.error);
