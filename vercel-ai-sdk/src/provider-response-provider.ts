import { LanguageModelV3, LanguageModelV3CallOptions, LanguageModelV3GenerateResult, LanguageModelV3StreamResult } from "@ai-sdk/provider";
import { Mem0ProviderSettings } from "./mem0-provider";
import { createOpenAI, OpenAIProviderSettings } from "@ai-sdk/openai";
import { CohereProviderSettings, createCohere } from "@ai-sdk/cohere";
import { AnthropicProviderSettings, createAnthropic } from "@ai-sdk/anthropic";
import { createGoogleGenerativeAI, GoogleGenerativeAIProviderSettings } from "@ai-sdk/google";
import { createGroq, GroqProviderSettings } from "@ai-sdk/groq";

// Define a private provider field
class Mem0AITextGenerator implements LanguageModelV3 {
    readonly specificationVersion = "v3";
    readonly modelId: string;
    readonly provider = "mem0";
    readonly supportedUrls: Record<string, RegExp[]> = {
        '*': [/.*/]
    };
    private languageModel: any; // Use any type to avoid version conflicts

    constructor(modelId: string, config: Mem0ProviderSettings, provider_config: ProviderSettings) {
        this.modelId = modelId;

        switch (config.provider) {
            case "openai":
                if(config?.modelType === "completion"){
                    this.languageModel = createOpenAI({
                        apiKey: config?.apiKey,
                        ...provider_config as OpenAIProviderSettings,
                    }).completion(modelId);
                } else if(config?.modelType === "chat"){
                    this.languageModel = createOpenAI({
                        apiKey: config?.apiKey,
                        ...provider_config as OpenAIProviderSettings,
                    }).chat(modelId);
                } else {
                    this.languageModel = createOpenAI({
                        apiKey: config?.apiKey,
                        ...provider_config as OpenAIProviderSettings,
                    }).languageModel(modelId);
                }
                break;
            case "cohere":
                this.languageModel = createCohere({
                    apiKey: config?.apiKey,
                    ...provider_config as CohereProviderSettings,
                })(modelId);
                break;
            case "anthropic":
                this.languageModel = createAnthropic({
                    apiKey: config?.apiKey,
                    ...provider_config as AnthropicProviderSettings,
                }).languageModel(modelId);
                break;
            case "groq":
                this.languageModel = createGroq({
                    apiKey: config?.apiKey,
                    ...provider_config as GroqProviderSettings,
                })(modelId);
                break;
            case "google":
                this.languageModel = createGoogleGenerativeAI({
                    apiKey: config?.apiKey,
                    ...provider_config as GoogleGenerativeAIProviderSettings,
                })(modelId);
                break;
            case "gemini":
                this.languageModel = createGoogleGenerativeAI({
                    apiKey: config?.apiKey,
                    ...provider_config as GoogleGenerativeAIProviderSettings,
                })(modelId);
                break;
            default:
                throw new Error("Invalid provider");
        }
    }

    async doGenerate(options: LanguageModelV3CallOptions): Promise<LanguageModelV3GenerateResult> {
        const result = await this.languageModel.doGenerate(options);
        return result as LanguageModelV3GenerateResult;
    }

    async doStream(options: LanguageModelV3CallOptions): Promise<LanguageModelV3StreamResult> {
        const result = await this.languageModel.doStream(options);
        return result as LanguageModelV3StreamResult;
    }
}

export type ProviderSettings = OpenAIProviderSettings | CohereProviderSettings | AnthropicProviderSettings | GroqProviderSettings | GoogleGenerativeAIProviderSettings;
export default Mem0AITextGenerator;
