#!/usr/bin/env node

/**
 * Jean Memory Desktop Extension MCP Server
 * This script acts as a proxy to connect Claude Desktop to Jean Memory's cloud MCP server
 */

const { spawn } = require('child_process');

// Get user ID from environment variable set by Claude Desktop
const userId = process.env.USER_ID;

if (!userId) {
  console.error('Error: Jean Memory User ID not provided. Please configure your User ID in the extension settings.');
  process.exit(1);
}

// Log startup (to stderr so it doesn't interfere with MCP protocol)
console.error(`[Jean Memory] Starting connection for user: ${userId.substring(0, 8)}...`);

// Construct the supergateway command to connect to Jean Memory with HTTP v2 transport
const args = [
  '-y',
  'supergateway', 
  '--stdio',
  `https://jean-memory-api.onrender.com/mcp/v2/claude/${userId}`
];

console.error(`[Jean Memory HTTP v2] Connecting to: https://jean-memory-api.onrender.com/mcp/v2/claude/${userId.substring(0, 8)}...`);

// Spawn supergateway process
const gateway = spawn('npx', args, {
  stdio: ['inherit', 'inherit', 'inherit'],
  env: { 
    ...process.env, 
    USER_ID: userId,
    // Ensure npm doesn't prompt for updates
    NO_UPDATE_NOTIFIER: '1',
    NPM_CONFIG_UPDATE_NOTIFIER: 'false'
  }
});

// Handle process events
gateway.on('close', (code) => {
  if (code !== 0) {
    console.error(`[Jean Memory] Connection closed with code ${code}`);
  }
  process.exit(code);
});

gateway.on('error', (err) => {
  console.error(`[Jean Memory] Failed to start connection: ${err.message}`);
  console.error(`[Jean Memory] Please check your internet connection and try again.`);
  process.exit(1);
});

// Handle termination signals
process.on('SIGTERM', () => {
  console.error('[Jean Memory] Received SIGTERM, shutting down...');
  gateway.kill('SIGTERM');
});

process.on('SIGINT', () => {
  console.error('[Jean Memory] Received SIGINT, shutting down...');
  gateway.kill('SIGINT');
}); 