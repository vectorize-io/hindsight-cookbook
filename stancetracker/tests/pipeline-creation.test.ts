/**
 * Integration tests for Vectorize pipeline creation
 *
 * These tests interact with the real Vectorize API to verify:
 * - Connector creation (source with WEB_CRAWLER, destination with VECTORIZE, AI platform)
 * - Pipeline creation and configuration
 * - Pipeline starting and management
 *
 * Prerequisites:
 * - VECTORIZE_API_KEY and VECTORIZE_ORG_ID environment variables set
 * - OPENAI_API_KEY set
 * - Note: VECTORIZE destination uses built-in storage (no external API key needed)
 * - Note: WEB_CRAWLER source uses built-in web scraper (no external API key needed)
 *
 * Note: These tests will create real resources in your Vectorize account.
 * Make sure to clean them up after testing.
 */

import { VectorizeClient } from '../lib/vectorize-client';

describe('Vectorize Pipeline Creation', () => {
  let client: VectorizeClient;
  const createdResourceIds: {
    pipelineIds: string[];
    sourceConnectorIds: string[];
    destinationConnectorIds: string[];
    aiPlatformConnectorIds: string[];
  } = {
    pipelineIds: [],
    sourceConnectorIds: [],
    destinationConnectorIds: [],
    aiPlatformConnectorIds: [],
  };

  beforeAll(() => {
    // Initialize the Vectorize client
    client = new VectorizeClient();
  });

  afterAll(async () => {
    // Clean up created resources
    console.log('\nCleaning up test resources...');

    // Delete pipelines first
    for (const pipelineId of createdResourceIds.pipelineIds) {
      try {
        await client.deletePipeline(pipelineId);
        console.log(`Deleted pipeline: ${pipelineId}`);
      } catch (error) {
        console.error(`Failed to delete pipeline ${pipelineId}:`, error);
      }
    }

    // Note: Connectors may need to be deleted manually via the Vectorize dashboard
    // or API, as they may be in use by pipelines
    console.log('\nNote: Source, destination, and AI platform connectors may need to be cleaned up manually.');
    console.log('Source connector IDs:', createdResourceIds.sourceConnectorIds);
    console.log('Destination connector IDs:', createdResourceIds.destinationConnectorIds);
    console.log('AI platform connector IDs:', createdResourceIds.aiPlatformConnectorIds);
  });

  describe('Connector Creation', () => {
    test('should create a WEB_CRAWLER source connector', async () => {
      const connectorName = `test-web-crawler-${Date.now()}`;
      const testUrls = ['https://example.com'];

      const response = await client.createWebCrawlerSourceConnector(
        connectorName,
        testUrls,
        {
          maxDepth: 2,
          maxUrls: 50,
        }
      );

      expect(response).toBeDefined();
      expect(response.connector).toBeDefined();
      expect(response.connector.id).toBeDefined();
      expect(response.connector.name).toBe(connectorName);

      createdResourceIds.sourceConnectorIds.push(response.connector.id);
      console.log(`Created WEB_CRAWLER connector: ${response.connector.id}`);
    }, 30000); // 30 second timeout for API call

    test('should create a VECTORIZE destination connector', async () => {
      const connectorName = `test-vectorize-${Date.now()}`;

      const response = await client.createVectorizeDestinationConnector(
        connectorName
      );

      expect(response).toBeDefined();
      expect(response.connector).toBeDefined();
      expect(response.connector.id).toBeDefined();
      expect(response.connector.name).toBe(connectorName);

      createdResourceIds.destinationConnectorIds.push(response.connector.id);
      console.log(`Created VECTORIZE connector: ${response.connector.id}`);
    }, 30000);

    test('should create an OpenAI AI platform connector', async () => {
      const openaiApiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY;
      if (!openaiApiKey) {
        console.log('Skipping test: OPENAI_API_KEY not set');
        return;
      }

      const connectorName = `test-openai-${Date.now()}`;

      const response = await client.createOpenAIConnector(
        connectorName,
        openaiApiKey
      );

      expect(response).toBeDefined();
      expect(response.connector).toBeDefined();
      expect(response.connector.id).toBeDefined();
      expect(response.connector.name).toBe(connectorName);

      createdResourceIds.aiPlatformConnectorIds.push(response.connector.id);
      console.log(`Created OpenAI connector: ${response.connector.id}`);
    }, 30000);
  });

  describe('Pipeline Creation', () => {
    test('should create a complete pipeline with WEB_CRAWLER source and VECTORIZE destination', async () => {
      const openaiApiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY;

      if (!openaiApiKey) {
        console.log('Skipping test: Required API key not set (OPENAI_API_KEY or LLM_API_KEY)');
        return;
      }

      const pipelineName = `test-pipeline-${Date.now()}`;
      const testUrls = ['https://example.com/test-article'];

      const result = await client.createCompletePipeline({
        name: pipelineName,
        sourceUrls: testUrls,
        openaiApiKey,
        crawlerConfig: {
          maxDepth: 2,
          maxUrls: 50,
        },
        schedule: {
          enabled: false, // Don't enable scheduling for test
        },
      });

      // Verify pipeline was created
      expect(result.pipeline).toBeDefined();
      expect(result.pipeline.data).toBeDefined();
      expect(result.pipeline.data.id).toBeDefined();
      expect(result.pipeline.data.name).toBe(pipelineName);

      // Verify connectors were created
      expect(result.sourceConnector.connector.id).toBeDefined();
      expect(result.destinationConnector.connector.id).toBeDefined();
      expect(result.aiPlatformConnector.connector.id).toBeDefined();

      // Track resources for cleanup
      createdResourceIds.pipelineIds.push(result.pipeline.data.id);
      createdResourceIds.sourceConnectorIds.push(result.sourceConnector.connector.id);
      createdResourceIds.destinationConnectorIds.push(result.destinationConnector.connector.id);
      createdResourceIds.aiPlatformConnectorIds.push(result.aiPlatformConnector.connector.id);

      console.log(`Created complete pipeline with WEB_CRAWLER source: ${result.pipeline.data.id}`);
      console.log(`  Source connector (WEB_CRAWLER): ${result.sourceConnector.connector.id}`);
      console.log(`  Destination connector (VECTORIZE): ${result.destinationConnector.connector.id}`);
      console.log(`  AI platform connector: ${result.aiPlatformConnector.connector.id}`);
    }, 60000); // 60 second timeout for multiple API calls
  });

  describe('Pipeline Management', () => {
    let testPipelineId: string;

    beforeAll(async () => {
      // Create a test pipeline
      const openaiApiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY;

      if (!openaiApiKey) {
        console.log('Skipping pipeline management tests: Required API key not set');
        return;
      }

      const result = await client.createCompletePipeline({
        name: `test-mgmt-pipeline-${Date.now()}`,
        sourceUrls: ['https://example.com'],
        openaiApiKey,
        crawlerConfig: {
          maxDepth: 2,
          maxUrls: 50,
        },
        schedule: { enabled: false },
      });

      testPipelineId = result.pipeline.data.id;
      createdResourceIds.pipelineIds.push(testPipelineId);
      createdResourceIds.sourceConnectorIds.push(result.sourceConnector.connector.id);
      createdResourceIds.destinationConnectorIds.push(result.destinationConnector.connector.id);
      createdResourceIds.aiPlatformConnectorIds.push(result.aiPlatformConnector.connector.id);
    });

    test('should start a pipeline', async () => {
      if (!testPipelineId) {
        console.log('Skipping test: Test pipeline not created');
        return;
      }

      const response = await client.startPipeline(testPipelineId);

      expect(response).toBeDefined();
      console.log(`Started pipeline: ${testPipelineId}`);
    }, 30000);

    test('should get pipeline details', async () => {
      if (!testPipelineId) {
        console.log('Skipping test: Test pipeline not created');
        return;
      }

      const response = await client.getPipeline(testPipelineId);

      expect(response).toBeDefined();
      expect(response.data).toBeDefined();
      expect(response.data.id).toBe(testPipelineId);

      console.log(`Retrieved pipeline details for: ${testPipelineId}`);
    }, 30000);

    test('should list all pipelines', async () => {
      const response = await client.listPipelines();

      expect(response).toBeDefined();
      expect(response.data).toBeDefined();
      expect(Array.isArray(response.data)).toBe(true);

      console.log(`Found ${response.data.length} pipelines in organization`);
    }, 30000);

    test('should stop a pipeline', async () => {
      if (!testPipelineId) {
        console.log('Skipping test: Test pipeline not created');
        return;
      }

      // Give pipeline time to start before stopping
      await new Promise(resolve => setTimeout(resolve, 2000));

      const response = await client.stopPipeline(testPipelineId);

      expect(response).toBeDefined();
      console.log(`Stopped pipeline: ${testPipelineId}`);
    }, 30000);
  });
});
