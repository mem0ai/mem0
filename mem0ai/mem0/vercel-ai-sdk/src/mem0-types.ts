import { Mem0ProviderSettings } from "./mem0-provider";
import { OpenAIChatSettings } from "@ai-sdk/openai/internal";
import { AnthropicMessagesSettings } from "@ai-sdk/anthropic/internal";
import {
  LanguageModelV1
} from "@ai-sdk/provider";

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
  output_format?: string;
}

export interface Mem0ChatConfig extends Mem0ConfigSettings, Mem0ProviderSettings {}

export interface Mem0Config extends Mem0ConfigSettings {}
export interface Mem0ChatSettings extends OpenAIChatSettings, AnthropicMessagesSettings, Mem0ConfigSettings {}

export interface Mem0StreamResponse extends Awaited<ReturnType<LanguageModelV1['doStream']>> {
  memories: any;
}
