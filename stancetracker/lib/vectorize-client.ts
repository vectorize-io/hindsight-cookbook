import {
  Configuration,
  PipelinesApi,
  SourceConnectorsApi,
  DestinationConnectorsApi,
  AIPlatformConnectorsApi,
  type PipelineConfigurationSchema,
  type CreatePipelineResponse,
  type GetPipelinesResponse,
  type GetPipelineResponse,
  type DeletePipelineResponse,
  type StartPipelineResponse,
  type StopPipelineResponse,
  type RetrieveDocumentsRequest,
  type RetrieveDocumentsResponse,
  type CreateSourceConnectorRequest,
  type CreateSourceConnectorResponse,
  type CreateDestinationConnectorRequest,
  type CreateDestinationConnectorResponse,
  type CreateAIPlatformConnectorRequest,
  type CreateAIPlatformConnectorResponse,
} from '@vectorize-io/vectorize-client';

const VECTORIZE_API_KEY = process.env.VECTORIZE_API_KEY;
const VECTORIZE_ORG_ID = process.env.VECTORIZE_ORG_ID;

export interface VectorizeDocument {
  id: string;
  text: string;
  metadata?: Record<string, any>;
}

export interface VectorizeSearchResult {
  id: string;
  text: string;
  metadata?: Record<string, any>;
  score: number;
}

export interface VectorizePipelineConfig {
  name: string;
  sourceConnectorId: string;
  destinationConnectorId: string;
  aiPlatformConnectorId: string;
  schedule?: {
    enabled: boolean;
    cronExpression?: string;
  };
}

export interface VectorizePipeline {
  id: string;
  name: string;
  status: 'active' | 'stopped' | 'error';
  created_at: string;
  last_run?: string;
  next_run?: string;
  documents_processed?: number;
}

export class VectorizeClient {
  private apiKey: string;
  private orgId: string;
  private pipelinesApi: PipelinesApi;
  private sourceConnectorsApi: SourceConnectorsApi;
  private destinationConnectorsApi: DestinationConnectorsApi;
  private aiPlatformConnectorsApi: AIPlatformConnectorsApi;

  constructor(apiKey?: string, orgId?: string) {
    this.apiKey = apiKey || VECTORIZE_API_KEY || '';
    this.orgId = orgId || VECTORIZE_ORG_ID || '';

    if (!this.apiKey) {
      throw new Error('Vectorize API key is required');
    }
    if (!this.orgId) {
      throw new Error('Vectorize organization ID is required');
    }

    // Initialize the official Vectorize client
    const config = new Configuration({
      accessToken: this.apiKey,
    });

    this.pipelinesApi = new PipelinesApi(config);
    this.sourceConnectorsApi = new SourceConnectorsApi(config);
    this.destinationConnectorsApi = new DestinationConnectorsApi(config);
    this.aiPlatformConnectorsApi = new AIPlatformConnectorsApi(config);
  }

  /**
   * Create a new pipeline with the specified configuration
   */
  async createPipeline(config: PipelineConfigurationSchema): Promise<CreatePipelineResponse> {
    const response = await this.pipelinesApi.createPipeline({
      organizationId: this.orgId,
      pipelineConfigurationSchema: config,
    });
    return response;
  }

  /**
   * Get a specific pipeline by ID
   */
  async getPipeline(pipelineId: string): Promise<GetPipelineResponse> {
    const response = await this.pipelinesApi.getPipeline({
      organizationId: this.orgId,
      pipelineId,
    });
    return response;
  }

  /**
   * List all pipelines in the organization
   */
  async listPipelines(workspaceId?: string): Promise<GetPipelinesResponse> {
    const response = await this.pipelinesApi.getPipelines({
      organizationId: this.orgId,
      workspaceId,
    });
    return response;
  }

  /**
   * Delete a pipeline
   */
  async deletePipeline(pipelineId: string): Promise<DeletePipelineResponse> {
    const response = await this.pipelinesApi.deletePipeline({
      organizationId: this.orgId,
      pipelineId,
    });
    return response;
  }

  /**
   * Start/trigger a pipeline to run
   */
  async startPipeline(pipelineId: string): Promise<StartPipelineResponse> {
    const response = await this.pipelinesApi.startPipeline({
      organizationId: this.orgId,
      pipelineId,
    });
    return response;
  }

  /**
   * Stop/pause a pipeline
   */
  async stopPipeline(pipelineId: string): Promise<StopPipelineResponse> {
    const response = await this.pipelinesApi.stopPipeline({
      organizationId: this.orgId,
      pipelineId,
    });
    return response;
  }

  /**
   * Retrieve/search documents from a pipeline
   */
  async retrieveDocuments(
    pipelineId: string,
    request: RetrieveDocumentsRequest
  ): Promise<RetrieveDocumentsResponse> {
    const response = await this.pipelinesApi.retrieveDocuments({
      organizationId: this.orgId,
      pipelineId,
      retrieveDocumentsRequest: request,
    });
    return response;
  }

  /**
   * Get pipeline events/logs
   */
  async getPipelineEvents(pipelineId: string, nextToken?: string) {
    const response = await this.pipelinesApi.getPipelineEvents({
      organizationId: this.orgId,
      pipelineId,
      nextToken,
    });
    return response;
  }

  /**
   * Get pipeline metrics
   */
  async getPipelineMetrics(pipelineId: string) {
    const response = await this.pipelinesApi.getPipelineMetrics({
      organizationId: this.orgId,
      pipelineId,
    });
    return response;
  }

  // ============================================================================
  // Connector Management Methods
  // ============================================================================

  /**
   * Create a WEB_CRAWLER source connector for web scraping using built-in crawler
   * @param name Name for the connector
   * @param urls URLs to crawl (seed URLs to start crawling from)
   * @param config Optional configuration for the crawler
   * @param workspaceId Optional workspace ID
   */
  async createWebCrawlerSourceConnector(
    name: string,
    urls: string[],
    config?: {
      allowedDomains?: string[];
      forbiddenPaths?: string[];
      minTimeBetweenRequests?: number;
      maxErrorCount?: number;
      maxUrls?: number;
      maxDepth?: number;
      reindexIntervalSeconds?: number;
    },
    workspaceId?: string
  ): Promise<CreateSourceConnectorResponse> {
    const connectorRequest: CreateSourceConnectorRequest = {
      name,
      type: 'WEB_CRAWLER',
      config: {
        seedUrls: urls,
        ...config,
      },
    };

    const response = await this.sourceConnectorsApi.createSourceConnector({
      organizationId: this.orgId,
      createSourceConnectorRequest: connectorRequest,
      workspaceId,
    });

    return response;
  }

  /**
   * @deprecated Use createWebCrawlerSourceConnector instead
   * Create a Firecrawl source connector for web scraping
   * @param name Name for the connector
   * @param url URL to scrape (can be a single page or domain to crawl)
   * @param apiKey Firecrawl API key
   * @param endpoint Either 'Scrape' for single page or 'Crawl' for full site
   * @param workspaceId Optional workspace ID
   */
  async createFirecrawlSourceConnector(
    name: string,
    url: string,
    apiKey: string,
    endpoint: 'Scrape' | 'Crawl' = 'Scrape',
    workspaceId?: string
  ): Promise<CreateSourceConnectorResponse> {
    const connectorRequest: CreateSourceConnectorRequest = {
      name,
      type: 'FIRECRAWL',
      config: {
        apiKey,
      },
    };

    const response = await this.sourceConnectorsApi.createSourceConnector({
      organizationId: this.orgId,
      createSourceConnectorRequest: connectorRequest,
      workspaceId,
    });

    return response;
  }

  /**
   * Create a VECTORIZE destination connector using built-in vector storage
   * @param name Name for the connector
   * @param workspaceId Optional workspace ID
   */
  async createVectorizeDestinationConnector(
    name: string,
    workspaceId?: string
  ): Promise<CreateDestinationConnectorResponse> {
    const connectorRequest: CreateDestinationConnectorRequest = {
      name,
      type: 'VECTORIZE',
      config: {},
    };

    const response = await this.destinationConnectorsApi.createDestinationConnector({
      organizationId: this.orgId,
      createDestinationConnectorRequest: connectorRequest,
      workspaceId,
    });

    return response;
  }

  /**
   * Create an OpenAI AI platform connector for embeddings
   * @param name Name for the connector
   * @param apiKey OpenAI API key
   * @param model Embedding model to use (default: text-embedding-3-small)
   * @param workspaceId Optional workspace ID
   */
  async createOpenAIConnector(
    name: string,
    apiKey: string,
    workspaceId?: string
  ): Promise<CreateAIPlatformConnectorResponse> {
    const connectorRequest: CreateAIPlatformConnectorRequest = {
      name,
      type: 'OPENAI',
      config: {
        key: apiKey,
      },
    };

    const response = await this.aiPlatformConnectorsApi.createAIPlatformConnector({
      organizationId: this.orgId,
      createAIPlatformConnectorRequest: connectorRequest,
      workspaceId,
    });

    return response;
  }

  /**
   * Create a complete pipeline with source, destination, and AI platform connectors
   * Uses the built-in WEB_CRAWLER source (no Firecrawl API key needed)
   * Uses the built-in VECTORIZE destination connector (no external API key needed)
   * @param config Pipeline configuration
   */
  async createCompletePipeline(config: {
    name: string;
    sourceUrls: string[];
    openaiApiKey: string;
    workspaceId?: string;
    crawlerConfig?: {
      allowedDomains?: string[];
      forbiddenPaths?: string[];
      minTimeBetweenRequests?: number;
      maxErrorCount?: number;
      maxUrls?: number;
      maxDepth?: number;
      reindexIntervalSeconds?: number;
    };
    schedule?: {
      enabled: boolean;
      cronExpression?: string;
    };
  }): Promise<{
    pipeline: CreatePipelineResponse;
    sourceConnector: CreateSourceConnectorResponse;
    destinationConnector: CreateDestinationConnectorResponse;
    aiPlatformConnector: CreateAIPlatformConnectorResponse;
  }> {
    try {
      // Create source connector (WEB_CRAWLER - built-in)
      console.log(`Creating WEB_CRAWLER source connector: ${config.name}-source`);
      const sourceConnector = await this.createWebCrawlerSourceConnector(
        `${config.name}-source`,
        config.sourceUrls,
        config.crawlerConfig,
        config.workspaceId
      );

      // Create destination connector (VECTORIZE - built-in storage)
      console.log(`Creating VECTORIZE destination connector: ${config.name}-destination`);
      const destinationConnector = await this.createVectorizeDestinationConnector(
        `${config.name}-destination`,
        config.workspaceId
      );

      // Create AI platform connector (OpenAI)
      console.log(`Creating OpenAI connector: ${config.name}-ai`);
      const aiPlatformConnector = await this.createOpenAIConnector(
        `${config.name}-ai`,
        config.openaiApiKey,
        config.workspaceId
      );

      // Create the pipeline linking all connectors
      console.log(`Creating pipeline: ${config.name}`);
      const pipelineConfig: PipelineConfigurationSchema = {
        pipelineName: config.name,
        sourceConnectors: [{
          id: sourceConnector.connector.id,
          type: 'WEB_CRAWLER',
          config: {
            seedUrls: config.sourceUrls,
            ...config.crawlerConfig,
          },
        }],
        destinationConnector: {
          id: destinationConnector.connector.id,
          type: 'VECTORIZE',
          config: {},
        },
        aiPlatformConnector: {
          id: aiPlatformConnector.connector.id,
          type: 'OPENAI',
          config: {} as any, // Config structure varies by AI platform
        },
        schedule: {
          type: config.schedule?.enabled ? 'custom' : 'manual',
        },
      };

      const pipeline = await this.createPipeline(pipelineConfig);

      return {
        pipeline,
        sourceConnector,
        destinationConnector,
        aiPlatformConnector,
      };
    } catch (error) {
      console.error('Error creating complete pipeline:', error);
      throw error;
    }
  }
}

export const vectorizeClient = new VectorizeClient();
