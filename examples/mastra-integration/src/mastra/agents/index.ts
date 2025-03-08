import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { mem0Tool } from '../tools';

export const mem0Agent = new Agent({
  name: 'Mem0 Agent',
  // You need to provide the instructions for the agent to save the memories in Mem0 explicitly
  instructions: `
    You are a helpful assistant that can answer questions based on memories from Mem0 and save all the information in Mem0.
  `,
  model: openai('gpt-4o'),
  tools: { mem0Tool },
});