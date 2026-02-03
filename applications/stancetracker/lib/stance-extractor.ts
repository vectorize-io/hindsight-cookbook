import { llmClient } from './llm-client';
import { hindsightClient } from './hindsight-client';
import { StancePoint, Reference } from '@/types';

export interface ExtractedStance {
  stance: string;
  stance_summary: string;
  confidence: number;
  reasoning?: string; // Added to track the thinking process
}

export class StanceExtractor {
  private sessionId?: string;

  constructor(sessionId?: string) {
    this.sessionId = sessionId;
  }

  async extractStance(
    candidate: string,
    topic: string,
    references: Reference[]
  ): Promise<ExtractedStance> {
    const prompt = this.buildExtractionPrompt(candidate, topic, references);

    const response = await llmClient.complete(
      [
        {
          role: 'system',
          content: `You are an expert political analyst tasked with extracting and summarizing a candidate's stance on issues based on source materials.
You must be objective, accurate, and cite specific evidence. Return your analysis in JSON format.`,
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      {
        temperature: 0.3,
        jsonMode: true,
      }
    );

    try {
      const parsed = JSON.parse(response.text);
      const initialResult = {
        stance: parsed.stance || parsed.detailed_stance || 'Unknown',
        stance_summary: parsed.summary || parsed.stance_summary || 'No summary available',
        confidence: parseFloat(parsed.confidence || '0.5'),
      };

      // If we have a sessionId, use Hindsight's think endpoint to refine confidence assessment
      if (this.sessionId) {
        try {
          console.log(`  Using Hindsight think endpoint for confidence assessment...`);
          const refinedResult = await this.assessConfidenceWithThinking(
            candidate,
            topic,
            references,
            initialResult
          );
          console.log(`  Refined confidence: ${initialResult.confidence.toFixed(2)} → ${refinedResult.confidence.toFixed(2)}`);
          return refinedResult;
        } catch (thinkError) {
          console.log(`  Hindsight thinking skipped:`, thinkError instanceof Error ? thinkError.message : thinkError);
          return initialResult;
        }
      }

      return initialResult;
    } catch (error) {
      console.error('Failed to parse LLM response:', error);
      return {
        stance: 'Unable to determine stance from sources',
        stance_summary: 'Insufficient or unclear information',
        confidence: 0.1,
      };
    }
  }

  /**
   * Use Hindsight's reflect endpoint to assess confidence through extended reasoning
   * This leverages memory recall and deeper analysis of source quality
   */
  private async assessConfidenceWithThinking(
    candidate: string,
    topic: string,
    references: Reference[],
    initialExtraction: ExtractedStance
  ): Promise<ExtractedStance> {
    const bankId = `scraper_${this.sessionId}`;

    // Build context about the sources
    const sourcesContext = references
      .map(
        (ref, idx) => `Source ${idx + 1}: ${ref.title} (${ref.source_type}, ${ref.published_date?.toISOString().split('T')[0] || 'date unknown'})`
      )
      .join('\n');

    const reflectQuery = `Assess the confidence level for this stance extraction on ${candidate}'s position on ${topic}.

Initial Extraction:
- Stance: ${initialExtraction.stance}
- Summary: ${initialExtraction.stance_summary}
- Initial Confidence: ${initialExtraction.confidence}

Available Sources (${references.length} total):
${sourcesContext}

Analyze and provide a refined confidence score (0.0-1.0) considering:
1. Source quality and credibility
2. Recency and relevance of sources
3. Consistency across sources
4. Directness of evidence (quotes vs. indirect reporting)
5. Any historical context from memory about ${candidate}'s positions

Return JSON with: { "refined_confidence": number, "reasoning": "explanation of confidence adjustment" }`;

    const reflectResult = await hindsightClient.reflect(bankId, reflectQuery, {
      budget: 'high', // Higher budget for thorough analysis
      context: `Evaluating stance extraction confidence for ${candidate} on ${topic}`,
    });

    console.log(`    Reflect reasoning: ${reflectResult.text.substring(0, 150)}...`);
    if (reflectResult.based_on) {
      console.log(`    Based on ${reflectResult.based_on.length} memory items`);
    }

    // Parse the reflection result to extract refined confidence
    try {
      // Try to extract JSON from the response
      const jsonMatch = reflectResult.text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        const refinedConfidence = parseFloat(parsed.refined_confidence);

        if (!isNaN(refinedConfidence) && refinedConfidence >= 0 && refinedConfidence <= 1) {
          return {
            ...initialExtraction,
            confidence: refinedConfidence,
            reasoning: parsed.reasoning || reflectResult.text,
          };
        }
      }

      // If JSON parsing fails, try to extract a number from the text
      const numberMatch = reflectResult.text.match(/(?:confidence|score)[:\s]+(\d+\.?\d*)/i);
      if (numberMatch) {
        const refinedConfidence = parseFloat(numberMatch[1]);
        if (refinedConfidence > 1) {
          // Assume it's a percentage
          return {
            ...initialExtraction,
            confidence: refinedConfidence / 100,
            reasoning: reflectResult.text,
          };
        } else if (refinedConfidence >= 0 && refinedConfidence <= 1) {
          return {
            ...initialExtraction,
            confidence: refinedConfidence,
            reasoning: reflectResult.text,
          };
        }
      }

      // If we can't parse a confidence score, use the reasoning to inform our decision
      // but keep the initial confidence with the reasoning attached
      return {
        ...initialExtraction,
        reasoning: reflectResult.text,
      };
    } catch (parseError) {
      console.log(`    Could not parse confidence from reflect result, keeping initial confidence`);
      return {
        ...initialExtraction,
        reasoning: reflectResult.text,
      };
    }
  }

  async detectStanceChange(
    previousStance: string,
    currentStance: string,
    candidate: string,
    topic: string
  ): Promise<{
    has_changed: boolean;
    change_description: string;
    change_magnitude: number;
  }> {
    const prompt = `Compare these two stances by ${candidate} on ${topic} and determine if there has been a meaningful change:

Previous Stance:
${previousStance}

Current Stance:
${currentStance}

Analyze:
1. Has there been a meaningful change in position?
2. If yes, describe the change concisely
3. Rate the magnitude of change from 0 (no change) to 1 (complete reversal)

Return JSON with: { "has_changed": boolean, "change_description": string, "change_magnitude": number }`;

    const response = await llmClient.complete(
      [
        {
          role: 'system',
          content: 'You are a political analyst comparing policy positions. Be precise and objective.',
        },
        {
          role: 'user',
          content: prompt,
        },
      ],
      {
        temperature: 0.2,
        jsonMode: true,
      }
    );

    try {
      const parsed = JSON.parse(response.text);
      return {
        has_changed: parsed.has_changed || false,
        change_description: parsed.change_description || 'No significant change detected',
        change_magnitude: parseFloat(parsed.change_magnitude || '0'),
      };
    } catch (error) {
      console.error('Failed to parse stance change response:', error);
      return {
        has_changed: false,
        change_description: 'Unable to determine change',
        change_magnitude: 0,
      };
    }
  }

  private buildExtractionPrompt(
    candidate: string,
    topic: string,
    references: Reference[]
  ): string {
    const sourcesText = references
      .map(
        (ref, idx) => `
[Source ${idx + 1}]
Title: ${ref.title}
Date: ${ref.published_date?.toISOString() || 'Unknown'}
Type: ${ref.source_type}
Excerpt: ${ref.excerpt || 'N/A'}
URL: ${ref.url}
`
      )
      .join('\n---\n');

    return `Extract ${candidate}'s stance on "${topic}" from the following sources:

${sourcesText}

Provide a JSON response with:
{
  "stance": "Detailed description of their current position based on the sources",
  "summary": "One-sentence summary of their stance",
  "confidence": 0.0-1.0 (how confident are you based on source quality and clarity)
}

Consider:
- Recency of sources (newer = more weight)
- Direct quotes vs. indirect reporting
- Consistency across sources
- Source credibility`;
  }
}

// Export the class for instantiation with sessionId
// Legacy singleton export for backward compatibility (without thinking features)
export const stanceExtractor = new StanceExtractor();
