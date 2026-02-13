import { z } from "zod";
import { Message } from "../types";

export interface ResponseFormat {
  type: string;
  schema?: z.ZodType;
}

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
    response_format?: ResponseFormat,
    tools?: any[],
  ): Promise<any>;
  generateChat(messages: Message[]): Promise<LLMResponse>;
}
