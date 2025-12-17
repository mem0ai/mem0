import { MCPServerConfig } from '../types';

export const mcpServers: Record<string, MCPServerConfig> = {
  mem0: {
    name: 'mem0',
    command: 'npx',
    args: ['-y', '@mem0/mcp-server'],
    env: {
      MEM0_API_KEY: process.env.MEM0_API_KEY || '',
      DEFAULT_USER_ID: process.env.MEM0_USER_ID || 'mem0-zai-crew',
    },
  },
  tavily: {
    name: 'tavily',
    command: 'npx',
    args: ['-y', '@tavily/mcp-server'],
    env: {
      TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
    },
  },
};

export function getMCPServerConfig(name: string): MCPServerConfig {
  const config = mcpServers[name];
  if (!config) {
    throw new Error(`MCP server not found: ${name}`);
  }
  return config;
}

export function getAllMCPServerConfigs(): MCPServerConfig[] {
  return Object.values(mcpServers);
}
