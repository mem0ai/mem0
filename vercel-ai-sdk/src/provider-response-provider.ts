import { LanguageModelV1, LanguageModelV1CallOptions, LanguageModelV1Prompt } from "ai";
import { Mem0ProviderSettings } from "./mem0-provider";
import { createOpenAI, OpenAIProviderSettings } from "@ai-sdk/openai";
import { CohereProviderSettings, createCohere } from "@ai-sdk/cohere";
import { AnthropicProviderSettings, createAnthropic } from "@ai-sdk/anthropic";
import { createGroq, GroqProviderSettings } from "@ai-sdk/groq";

export type Provider = ReturnType<typeof createOpenAI> | ReturnType<typeof createCohere> | ReturnType<typeof createAnthropic> | ReturnType<typeof createGroq> | any;
export type ProviderSettings = OpenAIProviderSettings | CohereProviderSettings | AnthropicProviderSettings | GroqProviderSettings;

const convertMessagesToMem0Format = (messages: LanguageModelV1Prompt) => {
    return messages.map((message) => {
      // If the content is a string, return it as is
      if (typeof message.content === "string") {
        return message;
      }
  
      // Flatten the content array into a single string
      if (Array.isArray(message.content)) {
        message.content = message.content
          .map((contentItem) => {
            if ("text" in contentItem) {
              return contentItem.text;
            }
            return "";
          })
          .join(" ");
      }
  
      const contentText = message.content;
  
      return {
        role: message.role,
        content: contentText,
      };
    });
  }

class Mem0AITextGenerator implements LanguageModelV1 {
    readonly specificationVersion = "v1";
    readonly defaultObjectGenerationMode = "json";
    readonly supportsImageUrls = false;
    readonly modelId: string;

    provider: Provider;
    provider_config?: ProviderSettings;
    config: Mem0ProviderSettings;

    constructor(modelId: string, config: Mem0ProviderSettings, provider_config: ProviderSettings) {
        switch (config.provider) {
            case "openai":
                this.provider = createOpenAI({
                    apiKey: config?.apiKey,
                    ...provider_config,
                }).languageModel;
                if(config?.modelType === "completion"){
                    this.provider = createOpenAI({
                        apiKey: config?.apiKey,
                        ...provider_config,
                    }).completion;
                }else if(config?.modelType === "chat"){
                    this.provider = createOpenAI({
                        apiKey: config?.apiKey,
                        ...provider_config,
                    }).chat;
                }
                break;
            case "cohere":
                this.provider = createCohere({
                    apiKey: config?.apiKey,
                    ...provider_config,
                });
                break;
            case "anthropic":
                this.provider = createAnthropic({
                    apiKey: config?.apiKey,
                    ...provider_config,
                }).languageModel;
                break;
            case "groq":
                this.provider = createGroq({
                    apiKey: config?.apiKey,
                    ...provider_config,
                });
                break;
            default:
                throw new Error("Invalid provider");
        }
        this.modelId = modelId;
        this.provider_config = provider_config;
        this.config = config!;
    }
    

    doGenerate(options: LanguageModelV1CallOptions): Promise<Awaited<ReturnType<LanguageModelV1['doGenerate']>>> {
        return this.provider(this.modelId, this.provider_config).doGenerate(options);
    }

    doStream(options: LanguageModelV1CallOptions): Promise<Awaited<ReturnType<LanguageModelV1['doStream']>>> {
        return this.provider(this.modelId, this.provider_config).doStream(options);
    }
}

export default Mem0AITextGenerator;
