import { Mem0ProviderSettings } from "./mem0-provider";
import { OpenAIProviderSettings } from "@ai-sdk/openai";
import { AnthropicProviderSettings } from "@ai-sdk/anthropic";
import { CohereProviderSettings } from "@ai-sdk/cohere";
import { GroqProviderSettings } from "@ai-sdk/groq";
import { GoogleGenerativeAIProviderSettings } from "@ai-sdk/google";
export type Mem0ChatModelId =
  | (string & NonNullable<unknown>);

export interface Mem0ConfigSettings {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  run_id?: string;
  metadata?: Record<string, any>;
  filters?: Record<string, any>;
  infer?: boolean;
  page?: number;
  page_size?: number;
  mem0ApiKey?: string;
  top_k?: number;
  threshold?: number;
  rerank?: boolean;
  host?: string;
}

export interface Mem0ChatConfig extends Mem0ConfigSettings, Mem0ProviderSettings {}

export type LLMProviderSettings = OpenAIProviderSettings | AnthropicProviderSettings | CohereProviderSettings | GroqProviderSettings | GoogleGenerativeAIProviderSettings;

export interface Mem0Config extends Mem0ConfigSettings {}
export interface Mem0ChatSettings extends Mem0ConfigSettings {}
