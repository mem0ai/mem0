import { Message } from "../types";

export interface LLMResponse {
  content: string;
  role: string;
}

export interface LLM {
  generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
  ): Promise<string>;
  generateChat(messages: Message[]): Promise<LLMResponse>;
}
