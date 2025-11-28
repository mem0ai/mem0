import Anthropic from '@anthropic-ai/sdk';
import { logger } from '../utils/logger';
import { Message } from '../types';
import { MCPClientManager } from '../mcp/client';

export interface ClaudeChatInput {
  userId: string;
  message: string;
  conversationHistory: Message[];
  onTextChunk?: (text: string) => void;
}

export class ClaudeClient {
  private client: Anthropic;
  private model: string;
  private maxTokens: number;
  private mcpManager: MCPClientManager;

  constructor() {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error('ANTHROPIC_API_KEY environment variable is required');
    }

    this.client = new Anthropic({ apiKey });
    this.model = process.env.CLAUDE_MODEL || 'claude-sonnet-4-5-20250929';
    this.maxTokens = Number(process.env.CLAUDE_MAX_TOKENS) || 4096;
    this.mcpManager = new MCPClientManager();

    // Initialize MCP manager
    this.initializeMCP();
  }

  private async initializeMCP(): Promise<void> {
    try {
      await this.mcpManager.initialize();
      logger.info('MCP tools initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize MCP tools:', error);
    }
  }

  async chat(input: ClaudeChatInput): Promise<string> {
    try {
      // Build conversation history
      const messages: Anthropic.MessageParam[] = [
        ...input.conversationHistory.map((msg) => ({
          role: msg.role,
          content: msg.content,
        })),
        {
          role: 'user' as const,
          content: input.message,
        },
      ];

      // Retrieve relevant memories from mem0
      const memories = await this.getRelevantMemories(input.userId, input.message);

      // Build system prompt with memory context
      const systemPrompt = this.buildSystemPrompt(memories);

      logger.debug('Sending request to Claude', {
        model: this.model,
        messageCount: messages.length,
      });

      // Call Claude API with streaming
      const response = await this.client.messages.create({
        model: this.model,
        max_tokens: this.maxTokens,
        system: systemPrompt,
        messages,
        stream: false, // We'll implement streaming in a future iteration
      });

      // Extract text response
      const textContent = response.content.find((block) => block.type === 'text');
      const responseText = textContent?.type === 'text' ? textContent.text : '';

      // Store interaction in memory
      await this.storeMemory(input.userId, input.message, responseText);

      if (input.onTextChunk) {
        input.onTextChunk(responseText);
      }

      return responseText;
    } catch (error) {
      logger.error('Claude chat error:', error);
      throw new Error(
        `Failed to get Claude response: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  private async getRelevantMemories(userId: string, query: string): Promise<string[]> {
    try {
      const result = await this.mcpManager.callTool('mem0', 'search-memories', {
        query,
        user_id: userId,
        limit: 5,
      });

      // Parse mem0 search results
      if (result && typeof result === 'object' && 'content' in result) {
        const content = (result as { content: Array<{ type: string; text: string }> }).content;
        const textContent = content.find((item) => item.type === 'text');
        if (textContent) {
          try {
            const parsed = JSON.parse(textContent.text);
            if (parsed.results && Array.isArray(parsed.results)) {
              return parsed.results.map((r: { memory: string }) => r.memory);
            }
          } catch {
            // If parsing fails, return empty array
          }
        }
      }

      return [];
    } catch (error) {
      logger.error('Error retrieving memories:', error);
      return [];
    }
  }

  private async storeMemory(userId: string, userMessage: string, assistantResponse: string): Promise<void> {
    try {
      await this.mcpManager.callTool('mem0', 'add-memory', {
        messages: [
          { role: 'user', content: userMessage },
          { role: 'assistant', content: assistantResponse },
        ],
        user_id: userId,
      });

      logger.debug('Stored conversation in memory');
    } catch (error) {
      logger.error('Error storing memory:', error);
      // Don't throw - memory storage is not critical for the response
    }
  }

  private buildSystemPrompt(memories: string[]): string {
    let prompt = `You are a helpful voice assistant with access to conversation memory and web search capabilities.

You should:
- Respond in a natural, conversational tone suitable for voice interaction
- Keep responses concise and clear
- Use memories to provide personalized, context-aware responses
- When needed, search the web for current information using available tools`;

    if (memories.length > 0) {
      prompt += `\n\n## Relevant Memories:\n`;
      memories.forEach((memory, index) => {
        prompt += `${index + 1}. ${memory}\n`;
      });
    }

    return prompt;
  }

  async close(): Promise<void> {
    await this.mcpManager.close();
  }
}
