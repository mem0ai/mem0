import dotenv from "dotenv";
import { MistralLLM } from "../../src/llms/mistral";

// Load environment variables
dotenv.config();

async function testMistral() {
  // Check for API key
  if (!process.env.MISTRAL_API_KEY) {
    console.error("MISTRAL_API_KEY environment variable is required");
    process.exit(1);
  }

  console.log("Testing Mistral LLM implementation...");

  // Initialize MistralLLM
  const mistral = new MistralLLM({
    apiKey: process.env.MISTRAL_API_KEY,
    model: "mistral-tiny-latest", // You can change to other models like mistral-small-latest
  });

  try {
    // Test simple chat completion
    console.log("Testing simple chat completion:");
    const chatResponse = await mistral.generateChat([
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "What is the capital of France?" },
    ]);

    console.log("Chat response:");
    console.log(`Role: ${chatResponse.role}`);
    console.log(`Content: ${chatResponse.content}\n`);

    // Test with functions/tools
    console.log("Testing tool calling:");
    const tools = [
      {
        type: "function",
        function: {
          name: "get_weather",
          description: "Get the current weather in a given location",
          parameters: {
            type: "object",
            properties: {
              location: {
                type: "string",
                description: "The city and state, e.g. San Francisco, CA",
              },
              unit: {
                type: "string",
                enum: ["celsius", "fahrenheit"],
                description: "The unit of temperature",
              },
            },
            required: ["location"],
          },
        },
      },
    ];

    const toolResponse = await mistral.generateResponse(
      [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "What's the weather like in Paris, France?" },
      ],
      undefined,
      tools,
    );

    console.log("Tool response:", toolResponse);

    console.log("\n✅ All tests completed successfully");
  } catch (error) {
    console.error("Error testing Mistral LLM:", error);
  }
}

testMistral().catch(console.error);
