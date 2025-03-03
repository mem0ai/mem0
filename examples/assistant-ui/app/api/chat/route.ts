/* eslint-disable @typescript-eslint/no-explicit-any */

import { createDataStreamResponse, jsonSchema, streamText } from "ai";
import { addMemories, getMemories } from "@mem0/vercel-ai-provider";
import { openai } from "@ai-sdk/openai";

export const runtime = "edge";
export const maxDuration = 30;

const retrieveMemories = (memories: any) => {
  if (memories.length === 0) return "";
  const systemPrompt =
    "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n";
  const memoriesText = memories
    .map((memory: any) => {
      return `Memory: ${memory.memory}\n\n`;
    })
    .join("\n\n");

  return `System Message: ${systemPrompt} ${memoriesText}`;
};

export async function POST(req: Request) {
  const { messages, system, tools, userId } = await req.json();

  const memories = await getMemories(messages, { user_id: userId });
  const mem0Instructions = retrieveMemories(memories);

  const result = streamText({
    model: openai("gpt-4o"),
    messages,
    // forward system prompt and tools from the frontend
    system: [system, mem0Instructions].filter(Boolean).join("\n"),
    tools: Object.fromEntries(
      Object.entries<{ parameters: unknown }>(tools).map(([name, tool]) => [
        name,
        {
          parameters: jsonSchema(tool.parameters!),
        },
      ])
    ),
  });

  const addMemoriesTask = addMemories(messages, { user_id: userId });
  return createDataStreamResponse({
    execute: async (writer) => {
      if (memories.length > 0) {
        writer.writeMessageAnnotation({
          type: "mem0-get",
          memories,
        });
      }

      result.mergeIntoDataStream(writer);

      const newMemories = await addMemoriesTask;
      if (newMemories.length > 0) {
        writer.writeMessageAnnotation({
          type: "mem0-update",
          memories: newMemories,
        });
      }
    },
  });
}
