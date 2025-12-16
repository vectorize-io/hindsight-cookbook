-- Demo Data Seed Script for Stance Tracker
-- This creates a sample tracking session with 3 candidates and their stance evolution over time

-- Store the session ID in a variable
DO $$
DECLARE
  v_session_id UUID;
  v_ref1 UUID; v_ref2 UUID; v_ref3 UUID; v_ref4 UUID; v_ref5 UUID;
  v_ref6 UUID; v_ref7 UUID; v_ref8 UUID; v_ref9 UUID; v_ref10 UUID;
  v_stance1 UUID; v_stance2 UUID; v_stance3 UUID; v_stance4 UUID; v_stance5 UUID;
  v_stance6 UUID; v_stance7 UUID; v_stance8 UUID; v_stance9 UUID; v_stance10 UUID;
BEGIN
  -- Create demo tracking session
  INSERT INTO tracking_sessions
  (country, state, city, topic, candidates, timespan_start, timespan_end, frequency, status)
  VALUES (
    'United States',
    'California',
    'San Francisco',
    'Climate Change Policy',
    ARRAY['Senator Jane Smith', 'Governor Bob Johnson', 'Representative Alice Chen'],
    '2024-06-01',
    '2024-11-23',
    'weekly',
    'active'
  ) RETURNING id INTO v_session_id;

  RAISE NOTICE 'Created session: %', v_session_id;

  -- Create references
  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/smith-june-2024',
    'Senator Smith Discusses Energy Policy at Town Hall',
    'Excerpt: Senator Smith emphasized the need to balance environmental concerns with economic growth during a town hall meeting.',
    '2024-06-15',
    'news'
  ) RETURNING id INTO v_ref1;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/smith-july-speech',
    'Smith Delivers Climate Speech at Stanford',
    'Excerpt: In a passionate speech at Stanford University, Senator Smith called for ambitious carbon reduction targets.',
    '2024-07-20',
    'speech'
  ) RETURNING id INTO v_ref2;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/smith-green-new-deal',
    'Senator Smith Endorses Modified Green New Deal',
    'Excerpt: Smith announced support for aggressive climate action including net-zero emissions by 2040.',
    '2024-09-10',
    'press_release'
  ) RETURNING id INTO v_ref3;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/johnson-june-interview',
    'Governor Johnson Interview on State Energy Policy',
    'Excerpt: Johnson discussed his moderate approach to climate policy and market-based solutions.',
    '2024-06-10',
    'interview'
  ) RETURNING id INTO v_ref4;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/johnson-energy-conference',
    'Johnson Speaks at Energy Industry Conference',
    'Excerpt: The governor expressed concerns about the economic impact of rapid climate regulations.',
    '2024-08-05',
    'speech'
  ) RETURNING id INTO v_ref5;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/johnson-delays-regulations',
    'Governor Johnson Delays New Climate Regulations',
    'Excerpt: Johnson announced a delay in climate regulations citing need for more industry consultation.',
    '2024-10-15',
    'news'
  ) RETURNING id INTO v_ref6;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/chen-climate-bill',
    'Rep. Chen Introduces Comprehensive Climate Bill',
    'Excerpt: Representative Chen introduced legislation calling for 100% clean energy by 2035.',
    '2024-06-05',
    'press_release'
  ) RETURNING id INTO v_ref7;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/chen-climate-rally',
    'Chen Speaks at Youth Climate Rally',
    'Excerpt: Chen called climate change an existential threat at a youth-organized rally.',
    '2024-07-25',
    'speech'
  ) RETURNING id INTO v_ref8;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/chen-carbon-tax',
    'Chen Proposes Carbon Tax with Revenue Redistribution',
    'Excerpt: The representative unveiled a carbon tax plan with benefits for low-income communities.',
    '2024-09-15',
    'press_release'
  ) RETURNING id INTO v_ref9;

  INSERT INTO "references" (url, title, excerpt, published_date, source_type)
  VALUES (
    'https://example.com/chen-cop-statement',
    'Rep. Chen Issues Statement on Climate Summit',
    'Excerpt: Chen urged the U.S. to exceed Paris Agreement commitments following the summit.',
    '2024-11-01',
    'press_release'
  ) RETURNING id INTO v_ref10;

  -- Senator Jane Smith - Evolution from cautious to strong supporter
  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Senator Jane Smith',
    'Climate Change Policy',
    'Senator Smith has expressed cautious support for climate initiatives, emphasizing the need to balance environmental concerns with economic growth. She advocates for a gradual transition to renewable energy.',
    'Cautiously supportive, balanced approach',
    0.65,
    '2024-06-15'
  ) RETURNING id INTO v_stance1;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance1, v_ref1);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Senator Jane Smith',
    'Climate Change Policy',
    'In a recent speech, Senator Smith strengthened her position on climate action, calling for ambitious carbon reduction targets and increased federal investment in clean energy infrastructure.',
    'Strong support for climate action',
    0.80,
    '2024-07-20'
  ) RETURNING id INTO v_stance2;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance2, v_ref2);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Senator Jane Smith',
    'Climate Change Policy',
    'Senator Smith has endorsed a modified version of the Green New Deal, committing to aggressive climate action targets including net-zero emissions by 2040. She now advocates for rapid transition to renewable energy.',
    'Strong advocate for aggressive climate policy',
    0.90,
    '2024-09-10'
  ) RETURNING id INTO v_stance3;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance3, v_ref3);

  -- Governor Bob Johnson - Moderate to skeptical shift
  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Governor Bob Johnson',
    'Climate Change Policy',
    'Governor Johnson supports moderate climate policies, including state-level renewable energy incentives and emissions standards. He emphasizes practical, market-based solutions.',
    'Moderate support for climate action',
    0.70,
    '2024-06-10'
  ) RETURNING id INTO v_stance4;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance4, v_ref4);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Governor Bob Johnson',
    'Climate Change Policy',
    'At an energy conference, Governor Johnson expressed concerns about the pace of climate regulations, warning about potential economic impacts. He advocates for a slower, more measured approach to emissions reductions.',
    'Cautious, concerned about economic impact',
    0.55,
    '2024-08-05'
  ) RETURNING id INTO v_stance5;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance5, v_ref5);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Governor Bob Johnson',
    'Climate Change Policy',
    'Governor Johnson has delayed implementation of new climate regulations, citing economic concerns and the need for more industry input. He questions the feasibility of aggressive climate targets.',
    'Skeptical of aggressive climate policies',
    0.45,
    '2024-10-15'
  ) RETURNING id INTO v_stance6;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance6, v_ref6);

  -- Representative Alice Chen - Consistent strong support
  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Representative Alice Chen',
    'Climate Change Policy',
    'Representative Chen has introduced comprehensive climate legislation calling for 100% clean energy by 2035, significant investment in green infrastructure, and environmental justice provisions.',
    'Strong climate action advocate',
    0.95,
    '2024-06-05'
  ) RETURNING id INTO v_stance7;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance7, v_ref7);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Representative Alice Chen',
    'Climate Change Policy',
    'At a youth climate rally, Representative Chen reaffirmed her commitment to aggressive climate action, calling the climate crisis an existential threat requiring immediate, bold action.',
    'Urgent climate action needed',
    0.92,
    '2024-07-25'
  ) RETURNING id INTO v_stance8;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance8, v_ref8);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Representative Alice Chen',
    'Climate Change Policy',
    'Representative Chen has proposed a carbon tax with revenue redistribution to low-income communities, demonstrating continued strong commitment to climate action with emphasis on equity and justice.',
    'Climate justice champion',
    0.93,
    '2024-09-15'
  ) RETURNING id INTO v_stance9;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance9, v_ref9);

  INSERT INTO stance_points
  (session_id, candidate, topic, stance, stance_summary, confidence, timestamp)
  VALUES (
    v_session_id,
    'Representative Alice Chen',
    'Climate Change Policy',
    'Following the international climate summit, Representative Chen called for the U.S. to exceed its Paris Agreement commitments and lead global climate action through domestic example.',
    'Leading voice for climate action',
    0.94,
    '2024-11-01'
  ) RETURNING id INTO v_stance10;

  INSERT INTO stance_point_references (stance_point_id, reference_id)
  VALUES (v_stance10, v_ref10);

  RAISE NOTICE 'Demo data created successfully!';
  RAISE NOTICE 'Session ID: %', v_session_id;
  RAISE NOTICE 'Created 3 candidates with 10 stance points and 10 references';
END $$;
