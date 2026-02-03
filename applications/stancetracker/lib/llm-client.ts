const LLM_PROVIDER = process.env.LLM_PROVIDER || 'openai';
const LLM_API_KEY = process.env.LLM_API_KEY;
const LLM_MODEL = process.env.LLM_MODEL || 'gpt-4-turbo-preview';

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

interface CompletionResponse {
  text: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export class LLMClient {
  private provider: string;
  private apiKey: string;
  private model: string;

  constructor(provider?: string, apiKey?: string, model?: string) {
    this.provider = provider || LLM_PROVIDER;
    this.apiKey = apiKey || LLM_API_KEY || '';
    this.model = model || LLM_MODEL;

    if (!this.apiKey && this.provider !== 'ollama') {
      throw new Error('LLM API key is required');
    }
  }

  async complete(
    messages: Message[],
    options: {
      temperature?: number;
      maxTokens?: number;
      jsonMode?: boolean;
    } = {}
  ): Promise<CompletionResponse> {
    switch (this.provider) {
      case 'openai':
        return this.openAIComplete(messages, options);
      case 'anthropic':
        return this.anthropicComplete(messages, options);
      case 'groq':
        return this.groqComplete(messages, options);
      default:
        throw new Error(`Unsupported LLM provider: ${this.provider}`);
    }
  }

  private async openAIComplete(
    messages: Message[],
    options: any
  ): Promise<CompletionResponse> {
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature: options.temperature || 0.7,
        max_tokens: options.maxTokens || 2000,
        ...(options.jsonMode && { response_format: { type: 'json_object' } }),
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return {
      text: data.choices[0].message.content,
      usage: data.usage,
    };
  }

  private async anthropicComplete(
    messages: Message[],
    options: any
  ): Promise<CompletionResponse> {
    const systemMessages = messages.filter((m) => m.role === 'system');
    const conversationMessages = messages.filter((m) => m.role !== 'system');

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: this.model,
        messages: conversationMessages,
        system: systemMessages.map((m) => m.content).join('\n'),
        temperature: options.temperature || 0.7,
        max_tokens: options.maxTokens || 2000,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Anthropic API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return {
      text: data.content[0].text,
      usage: {
        prompt_tokens: data.usage.input_tokens,
        completion_tokens: data.usage.output_tokens,
        total_tokens: data.usage.input_tokens + data.usage.output_tokens,
      },
    };
  }

  private async groqComplete(
    messages: Message[],
    options: any
  ): Promise<CompletionResponse> {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature: options.temperature || 0.7,
        max_tokens: options.maxTokens || 2000,
        ...(options.jsonMode && { response_format: { type: 'json_object' } }),
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Groq API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return {
      text: data.choices[0].message.content,
      usage: data.usage,
    };
  }
}

export const llmClient = new LLMClient();
