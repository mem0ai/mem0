import MemoryClient from "mem0ai";
import { OpenAI } from "openai";
import { zodResponsesFunction } from "openai/helpers/zod";
import { z } from "zod";

const mem0Config = {
    apiKey: process.env.MEM0_API_KEY, // GET THIS API KEY FROM MEM0 (https://app.mem0.ai/dashboard/api-keys)
    user_id: "sample-user",
};

async function run() {
    // RESPONES WITHOUT MEMORIES
    console.log("\n\nRESPONES WITHOUT MEMORIES\n\n");
    await main();

    // ADDING SOME SAMPLE MEMORIES
    await addSampleMemories();

    // RESPONES WITH MEMORIES
    console.log("\n\nRESPONES WITH MEMORIES\n\n");
    await main(true);
}

// OpenAI Response Schema
const CarSchema = z.object({
  car_name: z.string(),
  car_price: z.string(),
  car_url: z.string(),
  car_image: z.string(),
  car_description: z.string(),
});

const Cars = z.object({
  cars: z.array(CarSchema),
});

async function main(memory = false) {
  const openAIClient = new OpenAI();
  const mem0Client = new MemoryClient(mem0Config);

  const input = "Suggest me some cars that I can buy today.";

  const tool = zodResponsesFunction({ name: "carRecommendations", parameters: Cars });

  // First, let's store the user's memories from user input if any
  await mem0Client.add([{
    role: "user",
    content: input,
  }], mem0Config);

  // Then search for relevant memories
  let relevantMemories = []
  if (memory) {
    relevantMemories = await mem0Client.search(input, mem0Config);
  }

  const response = await openAIClient.responses.create({
    model: "gpt-4o",
    tools: [{ type: "web_search_preview" }, tool],
    input: `${getMemoryString(relevantMemories)}\n${input}`,
  });

  console.log(response.output);
}

async function addSampleMemories() {
  const mem0Client = new MemoryClient(mem0Config);

  const myInterests = "I Love BMW, Audi and Porsche. I Hate Mercedes. I love Red cars and Maroon cars. I have a budget of 120K to 150K USD. I like Audi the most.";
  
  await mem0Client.add([{
    role: "user",
    content: myInterests,
  }], mem0Config);
}

const getMemoryString = (memories) => {
    const MEMORY_STRING_PREFIX = "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The MEMORIES of the USER are: \n\n";
    const memoryString = memories.map((mem) => `${mem.memory}`).join("\n") ?? "";
    return memoryString.length > 0 ? `${MEMORY_STRING_PREFIX}${memoryString}` : "";
};

run().catch(console.error);
