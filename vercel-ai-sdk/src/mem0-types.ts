import { Mem0ProviderSettings } from "./mem0-provider";
import { OpenAIProviderSettings } from "@ai-sdk/openai";
import { AnthropicProviderSettings } from "@ai-sdk/anthropic";
import { LanguageModelV2 } from '@ai-sdk/provider';
import { CohereProviderSettings } from "@ai-sdk/cohere";
import { GroqProviderSettings } from "@ai-sdk/groq";
export type Mem0ChatModelId =
  | (string & NonNullable<unknown>);

export interface Mem0ConfigSettings {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  run_id?: string;
  org_name?: string;
  project_name?: string;
  org_id?: string;
  project_id?: string;
  metadata?: Record<string, any>;
  filters?: Record<string, any>;
  infer?: boolean;
  page?: number;
  page_size?: number;
  mem0ApiKey?: string;
  top_k?: number;
  threshold?: number;
  rerank?: boolean;
  enable_graph?: boolean;
  host?: string;
  output_format?: string;
  filter_memories?: boolean;
  async_mode?: boolean;
}

export interface Mem0ChatConfig extends Mem0ConfigSettings, Mem0ProviderSettings {}

export interface LLMProviderSettings extends OpenAIProviderSettings, AnthropicProviderSettings, CohereProviderSettings, GroqProviderSettings {}

export interface Mem0Config extends Mem0ConfigSettings {}
export interface Mem0ChatSettings extends Mem0ConfigSettings {}

export interface Mem0StreamResponse extends Awaited<ReturnType<LanguageModelV2['doStream']>> {
  memories: any;
}
