import { LanguageModelV2Prompt } from '@ai-sdk/provider';
import { Mem0ConfigSettings } from './mem0-types';
import { loadApiKey } from '@ai-sdk/provider-utils';
interface Message {
    role: string;
    content: string | Array<{type: string, text: string}>;
}

const flattenPrompt = (prompt: LanguageModelV2Prompt) => {
    try {
        return prompt.map((part) => {
            if (part.role === "user") {
                return part.content
                    .filter((obj) => obj.type === 'text')
                    .map((obj) => obj.text)
                    .join(" ");
            }
            return "";
        }).join(" ");
    } catch (error) {
        console.error("Error in flattenPrompt:", error);
        return "";
    }
}

const convertToMem0Format = (messages: LanguageModelV2Prompt) => {
    try {
        return messages.flatMap((message: any) => {
            try {
                if (typeof message.content === 'string') {
                    return {
                        role: message.role,
                        content: message.content,
                    };
                }
                else {
                    return message.content.map((obj: any) => {
                        try {
                            if (obj.type === "text") {
                                return {
                                    role: message.role,
                                    content: obj.text,
                                };
                            }
                            return null;
                        } catch (error) {
                            console.error("Error processing content object:", error);
                            return null;
                        }
                    }).filter((item: null) => item !== null);
                }
            } catch (error) {
                console.error("Error processing message:", error);
                return [];
            }
        });
    } catch (error) {
        console.error("Error in convertToMem0Format:", error);
        return [];
    }
}

const searchInternalMemories = async (query: string, config?: Mem0ConfigSettings, top_k: number = 5) => {
    try {
        const filters: { OR: Array<{ [key: string]: string | undefined }> } = {
            OR: [],
        };
        if (config?.user_id) {
            filters.OR.push({
                user_id: config.user_id,
            });
        }
        if (config?.app_id) {
            filters.OR.push({
                app_id: config.app_id,
            });
        }
        if (config?.agent_id) {
            filters.OR.push({
                agent_id: config.agent_id,
            });
        }
        if (config?.run_id) {
            filters.OR.push({
                run_id: config.run_id,
            });
        }
        const org_project_filters = {
            org_id: config&&config.org_id,
            project_id: config&&config.project_id,
            org_name: !config?.org_id ? config&&config.org_name : undefined,
            project_name: !config?.org_id ? config&&config.project_name : undefined,
        }

        const apiKey = loadApiKey({
            apiKey: (config&&config.mem0ApiKey),
            environmentVariableName: "MEM0_API_KEY",
            description: "Mem0",
        });

        const options = {
            method: 'POST',
            headers: {
                Authorization: `Token ${apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query,
                filters,
                ...config,
                top_k: config&&config.top_k || top_k,
                version: "v2",
                output_format: "v1.1",
                ...org_project_filters
            }),
        };

        const baseUrl = config?.host || 'https://api.mem0.ai';
        const response = await fetch(`${baseUrl}/v2/memories/search/`, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error in searchInternalMemories:", error);
        throw error;
    }
}

const addMemories = async (messages: LanguageModelV2Prompt, config?: Mem0ConfigSettings) => {
    try {
        let finalMessages: Array<Message> = [];
        if (typeof messages === "string") {
            finalMessages = [{ role: "user", content: messages }];
        } else {
            finalMessages = convertToMem0Format(messages);
        }
        const response = await updateMemories(finalMessages, config);
        return response;
    } catch (error) {
        console.error("Error in addMemories:", error);
        throw error;
    }
}

const updateMemories = async (messages: Array<Message>, config?: Mem0ConfigSettings) => {
    try {
        const apiKey = loadApiKey({
            apiKey: (config&&config.mem0ApiKey),
            environmentVariableName: "MEM0_API_KEY",
            description: "Mem0",
        });

        const options = {
            method: 'POST',
            headers: {
                Authorization: `Token ${apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({messages, ...config}),
        };

        const baseUrl = config?.host || 'https://api.mem0.ai';
        const response = await fetch(`${baseUrl}/v1/memories/`, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error in updateMemories:", error);
        throw error;
    }
}

const retrieveMemories = async (prompt: LanguageModelV2Prompt | string, config?: Mem0ConfigSettings) => {
    try {
        const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
        const systemPrompt = "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n";
        
        const memories = await searchInternalMemories(message, config);
        let memoriesText1 = "";
        let memoriesText2 = "";
        let graphPrompt = "";

        try {
            memoriesText1 = memories?.results?.map((memory: any) => {
                return `Memory: ${memory.memory}\n\n`;
            }).join("\n\n");

            if (config?.enable_graph) {
                memoriesText2 = memories?.relations?.map((memory: any) => {
                    return `Relation: ${memory.source} -> ${memory.relationship} -> ${memory.target} \n\n`;
                }).join("\n\n");
                graphPrompt = `HERE ARE THE GRAPHS RELATIONS FOR THE PREFERENCES OF THE USER:\n\n ${memoriesText2}`;
            }
        } catch (error) {
            console.error("Error while parsing memories:", error);
        }

        if (!memories || memories?.length === 0) {
            return "";
        }

        return `System Message: ${systemPrompt} ${memoriesText1} ${graphPrompt}`;
    } catch (error) {
        console.error("Error in retrieveMemories:", error);
        throw error;
    }
}

const getMemories = async (prompt: LanguageModelV2Prompt | string, config?: Mem0ConfigSettings) => {
    try {
        const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
        const memories = await searchInternalMemories(message, config);
        
        if (!config?.enable_graph) {
            return memories?.results;
        }
        return memories;
    } catch (error) {
        console.error("Error in getMemories:", error);
        throw error;
    }
}

const searchMemories = async (prompt: LanguageModelV2Prompt | string, config?: Mem0ConfigSettings) => {
    try {
        const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
        const memories = await searchInternalMemories(message, config);
        return memories;
    } catch (error) {
        console.error("Error in searchMemories:", error);
        return [];
    }
}

export {addMemories, updateMemories, retrieveMemories, flattenPrompt, searchMemories, getMemories};