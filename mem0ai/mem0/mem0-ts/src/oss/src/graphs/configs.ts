import { LLMConfig } from "../types";

export interface Neo4jConfig {
  url: string | null;
  username: string | null;
  password: string | null;
}

export interface GraphStoreConfig {
  provider: string;
  config: Neo4jConfig;
  llm?: LLMConfig;
  customPrompt?: string;
}

export function validateNeo4jConfig(config: Neo4jConfig): void {
  const { url, username, password } = config;
  if (!url || !username || !password) {
    throw new Error("Please provide 'url', 'username' and 'password'.");
  }
}

export function validateGraphStoreConfig(config: GraphStoreConfig): void {
  const { provider } = config;
  if (provider === "neo4j") {
    validateNeo4jConfig(config.config);
  } else {
    throw new Error(`Unsupported graph store provider: ${provider}`);
  }
}
