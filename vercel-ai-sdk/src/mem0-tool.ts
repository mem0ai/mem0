import { tool } from 'ai'
import { z } from 'zod'
import {
  addMemories,
  searchMemories,
  getMemory as getMemoryReq,
  deleteMemory as deleteMemoryReq,
} from './mem0-utils'
import type { Mem0ConfigSettings } from './mem0-types'

export const addMemoryTool = tool({
  description: 'add memory to mem0',
  parameters: z.object({
    text: z.string().describe('memory text to store'),
    user_id: z.string().optional().describe('unique user id'),
    config: z.any().optional(),
  }),
  async execute({ text, user_id, config }: { text: string; user_id?: string; config?: Mem0ConfigSettings }) {
    return await addMemories(
      [{ role: 'user', content: [{ type: 'text', text }] }],
      { ...config, user_id }
    )
  },
})

export const searchMemoryTool = tool({
  description: 'search memories in mem0',
  parameters: z.object({
    query: z.string().describe('search query'),
    user_id: z.string().optional().describe('unique user id'),
    config: z.any().optional(),
  }),
  async execute({ query, user_id, config }: { query: string; user_id?: string; config?: Mem0ConfigSettings }) {
    return await searchMemories(query, { ...config, user_id })
  },
})

export const getMemoryTool = tool({
  description: 'get a memory by id from mem0',
  parameters: z.object({
    id: z.string().describe('memory id'),
    user_id: z.string().optional().describe('unique user id'),
    config: z.any().optional(),
  }),
  async execute({ id, user_id, config }: { id: string; user_id?: string; config?: Mem0ConfigSettings }) {
    return await getMemoryReq(id, { ...config, user_id })
  },
})

export const deleteMemoryTool = tool({
  description: 'delete a memory from mem0',
  parameters: z.object({
    id: z.string().describe('memory id to delete'),
    user_id: z.string().optional().describe('unique user id'),
    config: z.any().optional(),
  }),
  async execute({ id, user_id, config }: { id: string; user_id?: string; config?: Mem0ConfigSettings }) {
    return await deleteMemoryReq(id, { ...config, user_id })
  },
})

export const mem0tool = {
  addMemory: addMemoryTool,
  searchMemory: searchMemoryTool,
  getMemory: getMemoryTool,
  deleteMemory: deleteMemoryTool,
}

export const createMemoryTools = ({ userId }: { userId?: string } = {}) => {
  const addMemory = tool({
    description: 'add memory to mem0',
    parameters: z.object({
      text: z.string().describe('memory text to store'),
      config: z.any().optional(),
    }),
    async execute({ text, config }: { text: string; config?: Mem0ConfigSettings }) {
      return await addMemories(
        [{ role: 'user', content: [{ type: 'text', text }] }],
        { ...config, user_id: userId }
      )
    },
  })

  const searchMemory = tool({
    description: 'search memories in mem0',
    parameters: z.object({
      query: z.string().describe('search query'),
      config: z.any().optional(),
    }),
    async execute({ query, config }: { query: string; config?: Mem0ConfigSettings }) {
      return await searchMemories(query, { ...config, user_id: userId })
    },
  })

  const getMemoryToolWithUser = tool({
    description: 'get a memory by id from mem0',
    parameters: z.object({
      id: z.string().describe('memory id'),
      config: z.any().optional(),
    }),
    async execute({ id, config }: { id: string; config?: Mem0ConfigSettings }) {
      return await getMemoryReq(id, { ...config, user_id: userId })
    },
  })

  const deleteMemoryToolWithUser = tool({
    description: 'delete a memory from mem0',
    parameters: z.object({
      id: z.string().describe('memory id to delete'),
      config: z.any().optional(),
    }),
    async execute({ id, config }: { id: string; config?: Mem0ConfigSettings }) {
      return await deleteMemoryReq(id, { ...config, user_id: userId })
    },
  })

  return {
    addMemory,
    searchMemory,
    getMemory: getMemoryToolWithUser,
    deleteMemory: deleteMemoryToolWithUser,
  }
}
