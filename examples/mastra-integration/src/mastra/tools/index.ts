import { createTool } from '@mastra/core/tools';
import { z } from 'zod';
import { mem0 } from '../integrations';

export const mem0Tool = createTool({
  id: 'mem0',
  description: 'Use MEM0 to answer questions',
  inputSchema: z.object({
    question: z.string().describe('Question to answer or a fact to save'),
  }),
  outputSchema: z.object({
    answer: z.string().describe('Answer to the question'),
  }),
  execute: async ({context}) => {
    // If the question is a fact, save it in Mem0
    await mem0.createMemory(context.question);

    // Search for the question in Mem0
    const memory = await mem0.searchMemory(context.question);

    // Return the memory string with a simple prompt to be used in the final response
    return await Promise.resolve({
      answer: memory,
    });
  },
});