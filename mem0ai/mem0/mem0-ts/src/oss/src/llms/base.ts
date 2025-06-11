import { Message } from "../types";

export interface LLMResponse {
  content: string;
  role: string;
  toolCalls?: Array<{
    name: string;
    arguments: string;
  }>;
}

export interface LLM {
  generateResponse(
    messages: Array<{ role: string; content: string }>,
    response_format?: { type: string },
    tools?: any[],
  ): Promise<any>;
  generateChat(messages: Message[]): Promise<LLMResponse>;
}
