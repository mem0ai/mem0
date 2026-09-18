import { LLM } from "../llms/base";
import { OpenAILLM } from "../llms/openai";
import { Message } from "../types";

const get_image_description = async (image_url: string, llm?: LLM) => {
  // Use the configured LLM (which carries the caller's provider + apiKey), like
  // the Python parse_vision_messages does. Falling back to a bare OpenAI client
  // read only from the env, as before, ignored a provider/apiKey set via config
  // and forced OpenAI even for non-OpenAI setups.
  const visionLlm =
    llm ?? new OpenAILLM({ apiKey: process.env.OPENAI_API_KEY });
  const response = await visionLlm.generateResponse([
    {
      role: "user",
      content:
        "Provide a description of the image and do not include any additional text.",
    },
    {
      role: "user",
      content: { type: "image_url", image_url: { url: image_url } },
    },
  ]);
  return response;
};

const parse_vision_messages = async (messages: Message[], llm?: LLM) => {
  const parsed_messages: Message[] = [];
  for (const message of messages) {
    // Preserve system messages (they carry extraction context/instructions),
    // matching the Python parse_vision_messages. Dropping them silently stripped
    // caller-provided system context before the extraction pipeline.
    if (message.role === "system") {
      parsed_messages.push(message);
      continue;
    }

    if (
      typeof message.content === "object" &&
      message.content.type === "image_url"
    ) {
      const imageUrl = message.content.image_url?.url;
      if (!imageUrl) {
        throw new Error("image_url content part is missing image_url.url");
      }
      const description = await get_image_description(imageUrl, llm);
      parsed_messages.push({
        role: message.role,
        content:
          typeof description === "string"
            ? description
            : JSON.stringify(description),
      });
    } else {
      parsed_messages.push(message);
    }
  }
  return parsed_messages;
};

export { parse_vision_messages };
