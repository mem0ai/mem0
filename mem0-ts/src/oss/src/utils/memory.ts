import { OpenAILLM } from "../llms/openai";
import { Message } from "../types";

const get_image_description = async (image_url: string) => {
  const llm = new OpenAILLM({
    apiKey: process.env.OPENAI_API_KEY,
  });
  const response = await llm.generateResponse([
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

const parse_vision_messages = async (messages: Message[]) => {
  const parsed_messages = [];
  for (const message of messages) {
    let new_message = {
      role: message.role,
      content: "",
    };
    if (message.role !== "system") {
      if (
        typeof message.content === "object" &&
        message.content.type === "image_url"
      ) {
        const description = await get_image_description(
          message.content.image_url.url,
        );
        new_message.content =
          typeof description === "string"
            ? description
            : JSON.stringify(description);
        parsed_messages.push(new_message);
      } else parsed_messages.push(message);
    }
  }
  return parsed_messages;
};

export { parse_vision_messages };
