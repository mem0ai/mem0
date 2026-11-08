import { mem0Provider } from "@mem0/eve";
import { defineMemory } from "eve/memory";
import { byPrincipal } from "eve/memory/scope";

export default defineMemory({
  description: "Recall and manage durable context for the current user.",
  provider: mem0Provider({
    apiKey: process.env.MEM0_API_KEY!,
  }),
  scope: byPrincipal,
});
