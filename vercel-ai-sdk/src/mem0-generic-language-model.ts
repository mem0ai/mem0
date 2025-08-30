/* eslint-disable camelcase */
import {
  LanguageModelV2CallOptions,
  LanguageModelV2Message,
  LanguageModelV2Source
} from '@ai-sdk/provider';

import { LanguageModelV2 } from '@ai-sdk/provider';
// streaming uses provider-native doStream; no middleware needed

import { Mem0ChatConfig, Mem0ChatModelId, Mem0ChatSettings, Mem0ConfigSettings, Mem0StreamResponse } from "./mem0-types";
import { Mem0ClassSelector } from "./mem0-provider-selector";
import { Mem0ProviderSettings } from "./mem0-provider";
import { addMemories, getMemories } from "./mem0-utils";

const generateRandomId = () => {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

export class Mem0GenericLanguageModel implements LanguageModelV2 {
  readonly specificationVersion = "v2";
  readonly defaultObjectGenerationMode = "json";
  // We don't support images for now
  readonly supportsImageUrls = false;
  // Allow All Media Types for now
  readonly supportedUrls: Record<string, RegExp[]> = {
    '*': [/.*/]
  };

  constructor(
    public readonly modelId: Mem0ChatModelId,
    public readonly settings: Mem0ChatSettings,
    public readonly config: Mem0ChatConfig,
    public readonly provider_config?: Mem0ProviderSettings
  ) {
    this.provider = config.provider ?? "openai";
  }

  provider: string;

  private async processMemories(messagesPrompts: LanguageModelV2Message[], mem0Config: Mem0ConfigSettings) {
    try {
    // Add New Memories
    addMemories(messagesPrompts, mem0Config).then((res) => {
      return res;
    }).catch((e) => {
      console.error("Error while adding memories");
      return { memories: [], messagesPrompts: [] };
    });

    // Get Memories
    let memories = await getMemories(messagesPrompts, mem0Config);

    const mySystemPrompt = "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n";

    const isGraphEnabled = mem0Config?.enable_graph;
  
    let memoriesText = "";
    let memoriesText2 = "";
    try {
      // @ts-ignore
      if (isGraphEnabled) {
        memoriesText = memories?.results?.map((memory: any) => {
          return `Memory: ${memory?.memory}\n\n`;
        }).join("\n\n");

        memoriesText2 = memories?.relations?.map((memory: any) => {
          return `Relation: ${memory?.source} -> ${memory?.relationship} -> ${memory?.target} \n\n`;
        }).join("\n\n");
      } else {
        memoriesText = memories?.map((memory: any) => {
          return `Memory: ${memory?.memory}\n\n`;
        }).join("\n\n");
      }
    } catch(e) {
      console.error("Error while parsing memories");
    }

    let graphPrompt = "";
    if (isGraphEnabled) {
      graphPrompt = `HERE ARE THE GRAPHS RELATIONS FOR THE PREFERENCES OF THE USER:\n\n ${memoriesText2}`;
    }

    const memoriesPrompt = `System Message: ${mySystemPrompt} ${memoriesText} ${graphPrompt} `;

    // System Prompt - The memories go as a system prompt
    const systemPrompt: LanguageModelV2Message = {
      role: "system",
      content: memoriesPrompt
    };

    // Add the system prompt to the beginning of the messages if there are memories
    if (memories?.length > 0) {
      messagesPrompts.unshift(systemPrompt);
    }

    if (isGraphEnabled) {
      memories = memories?.results;
    }

    return { memories, messagesPrompts };
    } catch(e) {
      console.error("Error while processing memories");
      return { memories: [], messagesPrompts };
    }
  }

  async doGenerate(options: LanguageModelV2CallOptions): Promise<Awaited<ReturnType<LanguageModelV2['doGenerate']>>> {
    try {   
      const provider = this.config.provider;
      const mem0_api_key = this.config.mem0ApiKey;
      
      const settings: Mem0ProviderSettings = {
        provider: provider,
        mem0ApiKey: mem0_api_key,
        apiKey: this.config.apiKey,
      }

      const mem0Config: Mem0ConfigSettings = {
        mem0ApiKey: mem0_api_key,
        ...this.config.mem0Config,
        ...this.settings,
      }

      const selector = new Mem0ClassSelector(this.modelId, settings, this.provider_config);
      
      let messagesPrompts = options.prompt;
      
      // Process memories and update prompts
      const { memories, messagesPrompts: updatedPrompts } = await this.processMemories(messagesPrompts, mem0Config);
      
      const model = selector.createProvider();

      const ans = await model.doGenerate({
        ...options,
        prompt: updatedPrompts,
      });
      
      // If there are no memories, return the original response
      if (!memories || memories?.length === 0) {
        return ans;
      }
      
      try {
        // Create sources array with existing sources
        const sources: LanguageModelV2Source[] = [
          {
            type: "source",
            title: "Mem0 Memories",
            sourceType: "url",
            id: "mem0-" + generateRandomId(),
            url: "https://app.mem0.ai",
            providerMetadata: {
              mem0: {
                memories: memories,
                memoriesText: memories
                  ?.map((memory: any) => memory?.memory)
                  .join("\n\n"),
              },
            },
          },
        ];
      } catch (e) {
        console.error("Error while creating sources");
      }
 
      return {
        ...ans,
        // sources
      };
    } catch (error) {
      // Handle errors properly
      console.error("Error in doGenerate:", error);
      throw new Error("Failed to generate response.");
    }
  }

  async doStream(options: LanguageModelV2CallOptions): Promise<Awaited<ReturnType<LanguageModelV2['doStream']>>> {
    try {
      const provider = this.config.provider;
      const mem0_api_key = this.config.mem0ApiKey;
      
      const settings: Mem0ProviderSettings = {
        provider: provider,
        mem0ApiKey: mem0_api_key,
        apiKey: this.config.apiKey,
        modelType: this.config.modelType,
      }

      const mem0Config: Mem0ConfigSettings = {
        mem0ApiKey: mem0_api_key,
        ...this.config.mem0Config,
        ...this.settings,
      }

      const selector = new Mem0ClassSelector(this.modelId, settings, this.provider_config);
      
      let messagesPrompts = options.prompt;
      
      // Process memories and update prompts
      const { memories, messagesPrompts: updatedPrompts } = await this.processMemories(messagesPrompts, mem0Config);

      const baseModel = selector.createProvider();

      // Use the provider's native streaming directly to avoid buffering
      const streamResponse = await baseModel.doStream({
        ...options,
        prompt: updatedPrompts,
      });

      // If there are no memories, return the original stream
      if (!memories || memories?.length === 0) {
        return streamResponse;
      }

      // Return stream untouched for true streaming behavior
      return {
        stream: streamResponse.stream,
        request: streamResponse.request,
        response: streamResponse.response,
      };
    } catch (error) {
      console.error("Error in doStream:", error);
      throw new Error("Streaming failed or method not implemented.");
    }
  }
}
