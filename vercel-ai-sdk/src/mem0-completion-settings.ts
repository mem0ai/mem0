import { OpenAICompletionSettings } from "@ai-sdk/openai/internal";

export type Mem0CompletionModelId =
  | "gpt-3.5-turbo"
  | (string & NonNullable<unknown>);

export interface Mem0CompletionSettings extends OpenAICompletionSettings {
  user_id?: string;
  app_id?: string;
  agent_id?: string;
  run_id?: string;
  org_name?: string;
  project_name?: string;
  mem0ApiKey?: string;
  structuredOutputs?: boolean;
  modelType?: string;
}

export interface Mem0Config extends Mem0CompletionSettings {}
