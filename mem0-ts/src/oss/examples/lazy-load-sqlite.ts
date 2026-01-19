// Test to verufy sqlite3 is lazy loaded

import { Memory } from "../src";

console.log("\nImport succeeded , sqlite3 was not eagerly loaded\n");

try {
    const memory = new Memory({
        embedder: {
            provider: "openai",
            config: {
                apiKey: ''
            }
        },
        vectorStore: {
            provider: "qdrant",
            config: {
                collectionName: "test",
                url: "http://localhost:6333"
            }
        },
        llm: {
            provider: 'openai',
            config: {
                apiKey: ''
            }
        }
    })

    console.log('\nMemory instantiated , no sqlite3 needed\n');
} catch (err) {
    console.error('\nError: ', err);
}