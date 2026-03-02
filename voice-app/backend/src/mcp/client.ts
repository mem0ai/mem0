import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { logger } from '../utils/logger';
import { MCPServerConfig } from '../types';
import { getAllMCPServerConfigs } from './servers';

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export class MCPClientManager {
  private clients: Map<string, Client> = new Map();
  private tools: Map<string, MCPTool> = new Map();

  async initialize(): Promise<void> {
    const serverConfigs = getAllMCPServerConfigs();

    for (const config of serverConfigs) {
      try {
        await this.connectServer(config);
      } catch (error) {
        logger.error(`Failed to connect to MCP server ${config.name}:`, error);
        // Continue with other servers even if one fails
      }
    }

    logger.info(`MCP Client Manager initialized with ${this.clients.size} servers`);
  }

  private async connectServer(config: MCPServerConfig): Promise<void> {
    logger.info(`Connecting to MCP server: ${config.name}`);

    const transport = new StdioClientTransport({
      command: config.command,
      args: config.args,
      env: { ...process.env, ...config.env },
    });

    const client = new Client(
      {
        name: `voice-app-${config.name}`,
        version: '1.0.0',
      },
      {
        capabilities: {},
      }
    );

    await client.connect(transport);

    // List available tools from this server
    const toolsResponse = await client.listTools();

    for (const tool of toolsResponse.tools) {
      const toolKey = `${config.name}.${tool.name}`;
      this.tools.set(toolKey, {
        name: tool.name,
        description: tool.description || '',
        inputSchema: tool.inputSchema as Record<string, unknown>,
      });
      logger.debug(`Registered tool: ${toolKey}`);
    }

    this.clients.set(config.name, client);
    logger.info(`Connected to MCP server: ${config.name} (${toolsResponse.tools.length} tools)`);
  }

  async callTool(serverName: string, toolName: string, args: Record<string, unknown>): Promise<unknown> {
    const client = this.clients.get(serverName);
    if (!client) {
      throw new Error(`MCP server not connected: ${serverName}`);
    }

    logger.debug(`Calling tool: ${serverName}.${toolName}`, { args });

    const result = await client.callTool({
      name: toolName,
      arguments: args,
    });

    logger.debug(`Tool result for ${serverName}.${toolName}:`, result);

    return result;
  }

  getTools(): MCPTool[] {
    return Array.from(this.tools.values());
  }

  getToolsByServer(serverName: string): MCPTool[] {
    const tools: MCPTool[] = [];
    for (const [key, tool] of this.tools.entries()) {
      if (key.startsWith(`${serverName}.`)) {
        tools.push(tool);
      }
    }
    return tools;
  }

  async close(): Promise<void> {
    for (const [name, client] of this.clients.entries()) {
      try {
        await client.close();
        logger.info(`Closed MCP client: ${name}`);
      } catch (error) {
        logger.error(`Error closing MCP client ${name}:`, error);
      }
    }
    this.clients.clear();
    this.tools.clear();
  }
}
