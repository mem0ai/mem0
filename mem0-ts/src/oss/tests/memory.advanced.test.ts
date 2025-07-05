// import { Memory } from '../src';
// import dotenv from 'dotenv';
// dotenv.config();

// describe('Memory Advanced Integration', () => {
//   const userId = 'advanced_user';

//   const vectorStoreConfigs = [
//     {
//       name: 'PGVector',
//       env: 'PGVECTOR_DB',
//       config: () => ({
//         version: 'v1.1',
//         embedder: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'text-embedding-3-small',
//           },
//         },
//         vectorStore: {
//           provider: 'pgvector',
//           config: {
//             collectionName: 'memories',
//             dimension: 1536,
//             dbname: process.env.PGVECTOR_DB,
//             user: process.env.PGVECTOR_USER,
//             password: process.env.PGVECTOR_PASSWORD,
//             host: process.env.PGVECTOR_HOST,
//             port: process.env.PGVECTOR_PORT ? parseInt(process.env.PGVECTOR_PORT) : 5432,
//             embeddingModelDims: 1536,
//             hnsw: true,
//           },
//         },
//         llm: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'gpt-4-turbo-preview',
//           },
//         },
//         historyDbPath: 'memory.db',
//       }),
//     },
//     {
//       name: 'Qdrant',
//       env: 'QDRANT_URL',
//       config: () => ({
//         version: 'v1.1',
//         embedder: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'text-embedding-3-small',
//           },
//         },
//         vectorStore: {
//           provider: 'qdrant',
//           config: {
//             collectionName: 'memories',
//             embeddingModelDims: 1536,
//             url: process.env.QDRANT_URL,
//             apiKey: process.env.QDRANT_API_KEY,
//             path: process.env.QDRANT_PATH,
//             host: process.env.QDRANT_HOST,
//             port: process.env.QDRANT_PORT ? parseInt(process.env.QDRANT_PORT) : undefined,
//             onDisk: true,
//           },
//         },
//         llm: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'gpt-4-turbo-preview',
//           },
//         },
//         historyDbPath: 'memory.db',
//       }),
//     },
//     {
//       name: 'Supabase',
//       env: 'SUPABASE_URL',
//       config: () => ({
//         version: 'v1.1',
//         embedder: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'text-embedding-3-small',
//           },
//         },
//         vectorStore: {
//           provider: 'supabase',
//           config: {
//             collectionName: 'memories',
//             embeddingModelDims: 1536,
//             supabaseUrl: process.env.SUPABASE_URL,
//             supabaseKey: process.env.SUPABASE_KEY,
//             tableName: 'memories',
//           },
//         },
//         llm: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'gpt-4-turbo-preview',
//           },
//         },
//         historyDbPath: 'memory.db',
//       }),
//     },
//     {
//       name: 'Redis',
//       env: 'REDIS_URL',
//       config: () => ({
//         version: 'v1.1',
//         embedder: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'text-embedding-3-small',
//           },
//         },
//         vectorStore: {
//           provider: 'redis',
//           config: {
//             collectionName: 'memories',
//             embeddingModelDims: 1536,
//             redisUrl: process.env.REDIS_URL,
//             username: process.env.REDIS_USERNAME,
//             password: process.env.REDIS_PASSWORD,
//           },
//         },
//         llm: {
//           provider: 'openai',
//           config: {
//             apiKey: process.env.OPENAI_API_KEY || '',
//             model: 'gpt-4-turbo-preview',
//           },
//         },
//         historyDbPath: 'memory.db',
//       }),
//     },
//   ];

//   it('should batch add and delete memories', async () => {
//     const memory = new Memory();
//     const batch = [
//       { role: 'user', content: 'Fact one.' },
//       { role: 'user', content: 'Fact two.' },
//       { role: 'assistant', content: 'Fact three.' },
//     ];
//     const result = await memory.add(batch, { userId });
//     expect(result.results.length).toBeGreaterThanOrEqual(2);
//     const ids = result.results.map(r => r.id);
//     for (const id of ids) {
//       await memory.delete(id);
//     }
//     const all = await memory.getAll({ userId });
//     expect(all.results.length).toBe(0);
//   });

//   it('should handle error on missing userId', async () => {
//     const memory = new Memory();
//     await expect(memory.add('No userId', {})).rejects.toThrow(/userId/i);
//   });

//   it('should handle update/delete of non-existent memory', async () => {
//     const memory = new Memory();
//     await expect(memory.update('nonexistent', 'data')).rejects.toThrow();
//     await expect(memory.delete('nonexistent')).rejects.toThrow();
//   });

//   for (const store of vectorStoreConfigs) {
//     const envSet = !!process.env[store.env];
//     const testName = `${store.name} vector store integration`;
//     (envSet ? it : it.skip)(testName, async () => {
//       const memory = new Memory(store.config());
//       const result = await memory.add('Vector store test', { userId });
//       expect(result.results.length).toBeGreaterThan(0);
//       const id = result.results[0].id;
//       const mem = await memory.get(id);
//       expect(mem).not.toBeNull();
//       await memory.delete(id);
//     });
//   }

//   const neo4jEnvSet = process.env.NEO4J_URL && process.env.NEO4J_USERNAME && process.env.NEO4J_PASSWORD;
//   (neo4jEnvSet ? it : it.skip)('Graph memory integration (Neo4j)', async () => {
//     const memory = new Memory({
//       version: 'v1.1',
//       embedder: {
//         provider: 'openai',
//         config: {
//           apiKey: process.env.OPENAI_API_KEY || '',
//           model: 'text-embedding-3-small',
//         },
//       },
//       vectorStore: {
//         provider: 'memory',
//         config: {
//           collectionName: 'memories',
//           dimension: 1536,
//         },
//       },
//       llm: {
//         provider: 'openai',
//         config: {
//           apiKey: process.env.OPENAI_API_KEY || '',
//           model: 'gpt-4-turbo-preview',
//         },
//       },
//       enableGraph: true,
//       graphStore: {
//         provider: 'neo4j',
//         config: {
//           url: process.env.NEO4J_URL,
//           username: process.env.NEO4J_USERNAME,
//           password: process.env.NEO4J_PASSWORD,
//         },
//         llm: {
//           provider: 'openai',
//           config: {
//             model: 'gpt-4-turbo-preview',
//           },
//         },
//       },
//       historyDbPath: 'memory.db',
//     });
//     const result = await memory.add('Alice is Bob\'s sister and works as a doctor.', { userId });
//     expect(result.relations).toBeDefined();
//     const search = await memory.search('Tell me about Bob\'s family', { userId });
//     expect(search.relations).toBeDefined();
//   });
// }); 