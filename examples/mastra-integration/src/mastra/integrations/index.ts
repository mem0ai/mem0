import { Mem0Integration } from "mem0-mastra";

export const mem0 = new Mem0Integration({
    config: {
        apiKey: process.env.MEM0_API_KEY || "",
        user_id: "test",
    },
});
