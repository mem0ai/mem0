import { tool } from 'ai'
import { z } from 'zod'
import { addMemories, searchMemories, getMemory, deleteMemory } from './mem0-utils'
import type { Mem0ConfigSettings } from './mem0-types'

export const addMemoryTool = tool({
  description: 'add memory to mem0',
  parameters: z.object({
    text: z.string().describe('memory text to store'),
    config: z.any().optional(),
  }),
  async execute({ text, config }: { text: string; config?: Mem0ConfigSettings }) {
    return await addMemories([{ role: 'user', content: [{ type: 'text', text }] }], config)
  },
})

export const searchMemoryTool = tool({
  description: 'search memories in mem0',
  parameters: z.object({
    query: z.string().describe('search query'),
    config: z.any().optional(),
  }),
  async execute({ query, config }: { query: string; config?: Mem0ConfigSettings }) {
    return await searchMemories(query, config)
  },
})

export const getMemoryTool = tool({
  description: 'get a memory by id from mem0',
  parameters: z.object({
    id: z.string().describe('memory id'),
    config: z.any().optional(),
  }),
  async execute({ id, config }: { id: string; config?: Mem0ConfigSettings }) {
    return await getMemory(id, config)
  },
})

export const deleteMemoryTool = tool({
  description: 'delete a memory from mem0',
  parameters: z.object({
    id: z.string().describe('memory id to delete'),
    config: z.any().optional(),
  }),
  async execute({ id, config }: { id: string; config?: Mem0ConfigSettings }) {
    return await deleteMemory(id, config)
  },
})
