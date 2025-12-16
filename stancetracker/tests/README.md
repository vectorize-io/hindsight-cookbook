# Vectorize Pipeline Tests

This directory contains integration tests for the Vectorize pipeline creation system.

## Prerequisites

Before running the tests, ensure you have the following environment variables set:

```bash
# Required for all tests
VECTORIZE_API_KEY=your_vectorize_api_key
VECTORIZE_ORG_ID=your_vectorize_org_id

# Required for connector and pipeline tests
FIRECRAWL_API_KEY=your_firecrawl_api_key
OPENAI_API_KEY=your_openai_api_key

# Note: VECTORIZE destination uses built-in storage (no external API key needed)
```

You can add these to your `.env` or `.env.local` file.

## Running Tests

### Install dependencies first

```bash
npm install
```

### Run all tests

```bash
npm test
```

### Run only pipeline creation tests

```bash
npm run test:pipeline
```

### Run tests in watch mode

```bash
npm run test:watch
```

## Test Structure

### pipeline-creation.test.ts

Integration tests for the complete Vectorize pipeline creation flow:

1. **Connector Creation Tests**
   - Create Firecrawl source connector
   - Create VECTORIZE destination connector (built-in storage)
   - Create OpenAI AI platform connector

2. **Pipeline Creation Tests**
   - Create a complete pipeline with all connectors
   - Verify all components are properly linked
   - Verify VECTORIZE destination is properly configured

3. **Pipeline Management Tests**
   - Start a pipeline
   - Get pipeline details
   - List all pipelines
   - Stop a pipeline

## Important Notes

- These are **integration tests** that interact with the real Vectorize API
- Tests will create actual resources in your Vectorize account
- Resources are automatically cleaned up after tests complete
- Some connectors may need manual cleanup via the Vectorize dashboard
- Tests have extended timeouts (30-60 seconds) to accommodate API response times
- If API keys are not set, tests will be skipped gracefully

## Cleanup

The test suite automatically cleans up pipelines after running. However, connectors may persist and need manual deletion through the Vectorize dashboard or API.

You can find the connector IDs in the test output to help with cleanup.
