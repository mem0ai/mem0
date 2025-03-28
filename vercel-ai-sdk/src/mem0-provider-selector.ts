import { Mem0ProviderSettings } from "./mem0-provider";
import Mem0AITextGenerator, { ProviderSettings } from "./provider-response-provider";
import { LanguageModelV1 } from "ai";

class Mem0ClassSelector {
    modelId: string;
    provider_wrapper: string;
    config: Mem0ProviderSettings;
    provider_config?: ProviderSettings;
    static supportedProviders = ["openai", "anthropic", "cohere", "groq"];

    constructor(modelId: string, config: Mem0ProviderSettings, provider_config?: ProviderSettings) {
        this.modelId = modelId;
        this.provider_wrapper = config.provider || "openai";
        this.provider_config = provider_config;
        if(config) this.config = config;
        else this.config = {
            provider: this.provider_wrapper,
        };

        // Check if provider_wrapper is supported
        if (!Mem0ClassSelector.supportedProviders.includes(this.provider_wrapper)) {
            throw new Error(`Model not supported: ${this.provider_wrapper}`);
        }
    }

    createProvider(): LanguageModelV1 {
        return new Mem0AITextGenerator(this.modelId, this.config , this.provider_config || {});
    }
}

export { Mem0ClassSelector };
