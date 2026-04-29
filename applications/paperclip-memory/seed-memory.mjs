/**
 * Seed memory into the bank that the @vectorize-io/hindsight-paperclip
 * plugin will recall from on the next run.
 *
 * The plugin uses bank IDs of the form `paperclip::{companyId}::{agentId}`
 * by default. Adjust COMPANY_ID / AGENT_ID below to match the values
 * Paperclip emits in `agent.run.started`.
 *
 * Usage:
 *   HINDSIGHT_URL=http://localhost:8888 \
 *     COMPANY_ID=acme-corp \
 *     AGENT_ID=eng-agent \
 *     node seed-memory.mjs
 *
 *   # With Hindsight Cloud:
 *   HINDSIGHT_URL=https://api.hindsight.vectorize.io \
 *     HINDSIGHT_API_KEY=hk_... \
 *     COMPANY_ID=acme-corp \
 *     AGENT_ID=eng-agent \
 *     node seed-memory.mjs
 */

const HINDSIGHT_URL = process.env.HINDSIGHT_URL ?? 'http://localhost:8888';
const HINDSIGHT_API_KEY = process.env.HINDSIGHT_API_KEY;
const COMPANY_ID = process.env.COMPANY_ID ?? 'acme-corp';
const AGENT_ID = process.env.AGENT_ID ?? 'eng-agent';
const BANK_ID = `paperclip::${COMPANY_ID}::${AGENT_ID}`;

const SAMPLE_RUNS = [
  {
    runId: 'run-001',
    summary:
      'Reviewed PR #142 (auth refactor). Required MFA on /admin routes; flagged ' +
      'session token rotation as a follow-up.',
  },
  {
    runId: 'run-002',
    summary:
      'Investigated flaky integration test test_session_expiry. Root cause: ' +
      'timezone-naive datetime comparison; replaced with timezone-aware UTC.',
  },
  {
    runId: 'run-003',
    summary:
      'Drafted release notes for v2.4.0. Highlighted MFA enforcement, dark-mode ' +
      'fix, and the Postgres 16 upgrade.',
  },
];

function headers() {
  const h = { 'Content-Type': 'application/json' };
  if (HINDSIGHT_API_KEY) h['Authorization'] = `Bearer ${HINDSIGHT_API_KEY}`;
  return h;
}

async function ensureBank() {
  const res = await fetch(`${HINDSIGHT_URL}/v1/default/banks`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ bank_id: BANK_ID }),
  });
  if (!res.ok && res.status !== 409) {
    throw new Error(`create-bank failed: ${res.status} ${await res.text()}`);
  }
}

async function retain(content, documentId) {
  const res = await fetch(
    `${HINDSIGHT_URL}/v1/default/banks/${encodeURIComponent(BANK_ID)}/memories/retain`,
    {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ content, document_id: documentId }),
    },
  );
  if (!res.ok) {
    throw new Error(`retain failed: ${res.status} ${await res.text()}`);
  }
}

async function recallSample() {
  const res = await fetch(
    `${HINDSIGHT_URL}/v1/default/banks/${encodeURIComponent(BANK_ID)}/memories/recall`,
    {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ query: 'recent decisions and follow-ups' }),
    },
  );
  if (!res.ok) {
    throw new Error(`recall failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

async function main() {
  console.log(`Seeding bank: ${BANK_ID}`);
  console.log(`Hindsight URL: ${HINDSIGHT_URL}\n`);

  await ensureBank();

  for (const run of SAMPLE_RUNS) {
    process.stdout.write(`  retain ${run.runId} ... `);
    await retain(run.summary, run.runId);
    console.log('ok');
  }

  console.log('\nVerifying with a recall ...');
  const result = await recallSample();
  const memories = result.memories ?? result.results ?? [];
  console.log(`Found ${memories.length} memory item(s).`);
  if (memories[0]) {
    console.log('First:', memories[0].content ?? memories[0]);
  }

  console.log(
    '\nNext run of the Paperclip agent for ' +
      `companyId=${COMPANY_ID} agentId=${AGENT_ID} will recall this context ` +
      'automatically via @vectorize-io/hindsight-paperclip.',
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
