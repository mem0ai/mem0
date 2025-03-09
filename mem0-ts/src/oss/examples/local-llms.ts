import { Memory } from "../src";
import { Ollama } from "ollama";
import * as readline from "readline";

const memory = new Memory({
  embedder: {
    provider: "ollama",
    config: {
      model: "nomic-embed-text:latest",
    },
  },
  vectorStore: {
    provider: "memory",
    config: {
      collectionName: "memories",
      dimension: 768, // since we are using nomic-embed-text
    },
  },
  llm: {
    provider: "ollama",
    config: {
      model: "llama3.1:8b",
    },
  },
  historyDbPath: "local-llms.db",
});

async function chatWithMemories(message: string, userId = "default_user") {
  const relevantMemories = await memory.search(message, { userId: userId });

  const memoriesStr = relevantMemories.results
    .map((entry) => `- ${entry.memory}`)
    .join("\n");

  const systemPrompt = `You are a helpful AI. Answer the question based on query and memories.
User Memories:
${memoriesStr}`;

  const messages = [
    { role: "system", content: systemPrompt },
    { role: "user", content: message },
  ];

  const ollama = new Ollama();
  const response = await ollama.chat({
    model: "llama3.1:8b",
    messages: messages,
  });

  const assistantResponse = response.message.content || "";

  messages.push({ role: "assistant", content: assistantResponse });
  await memory.add(messages, { userId: userId });

  return assistantResponse;
}

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("Chat with AI (type 'exit' to quit)");

  const askQuestion = (): Promise<string> => {
    return new Promise((resolve) => {
      rl.question("You: ", (input) => {
        resolve(input.trim());
      });
    });
  };

  try {
    while (true) {
      const userInput = await askQuestion();

      if (userInput.toLowerCase() === "exit") {
        console.log("Goodbye!");
        rl.close();
        break;
      }

      const response = await chatWithMemories(userInput, "sample_user");
      console.log(`AI: ${response}`);
    }
  } catch (error) {
    console.error("An error occurred:", error);
    rl.close();
  }
}

main().catch(console.error);
