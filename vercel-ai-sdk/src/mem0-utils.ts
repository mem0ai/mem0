import { LanguageModelV1Prompt } from 'ai';
import { Mem0ConfigSettings } from './mem0-types';
import { loadApiKey } from '@ai-sdk/provider-utils';
interface Message {
    role: string;
    content: string | Array<{type: string, text: string}>;
}

const flattenPrompt = (prompt: LanguageModelV1Prompt) => {
    return prompt.map((part) => {
        if (part.role === "user") {
            return part.content
                .filter((obj) => obj.type === 'text')
                .map((obj) => obj.text)
                .join(" ");
        }
        return "";
    }).join(" ");
}

const convertToMem0Format = (messages: LanguageModelV1Prompt) => {
  return messages.flatMap((message: any) => {
    if (typeof message.content === 'string') {
      return {
        role: message.role,
        content: message.content,
      };
    }
    else{
      return message.content.map((obj: any) => {
        if (obj.type === "text") {
          return {
            role: message.role,
            content: obj.text,
          };
        } else {
          return null; // Handle other cases or return null/undefined as needed
        }
      }).filter((item: null) => item !== null); // Filter out null values if necessary      
    }
})};

const searchInternalMemories = async (query: string, config?: Mem0ConfigSettings, top_k: number = 5)=> {
    const filters: { AND: Array<{ [key: string]: string | undefined }> } = {
      AND: [],
    };
    if (config?.user_id) {
      filters.AND.push({
        user_id: config.user_id,
      });
    }
    if (config?.app_id) {
      filters.AND.push({
        app_id: config.app_id,
      });
    }
    if (config?.agent_id) {
      filters.AND.push({
        agent_id: config.agent_id,
      });
    }
    if (config?.run_id) {
      filters.AND.push({
        run_id: config.run_id,
      });
    }
    const org_project_filters = {
      org_id: config&&config.org_id,
      project_id: config&&config.project_id,
      org_name: !config?.org_id ? config&&config.org_name : undefined,  // deprecated
      project_name: !config?.org_id ? config&&config.project_name : undefined, // deprecated
    }
    const options = {
        method: 'POST',
        // headers: {Authorization: `Token ${(config&&config.mem0ApiKey) || (typeof process !== 'undefined' && process.env && process.env.MEM0_API_KEY) || ""}`, 'Content-Type': 'application/json'}, 
        headers: {Authorization: `Token ${loadApiKey({
            apiKey: (config&&config.mem0ApiKey),
            environmentVariableName: "MEM0_API_KEY",
            description: "Mem0",
        })}`, 'Content-Type': 'application/json'}, 
        body: JSON.stringify({query, filters, ...config, top_k: config&&config.top_k || top_k, version: "v2", output_format: "v1.1", ...org_project_filters}),
    };
    const response  = await fetch('https://api.mem0.ai/v2/memories/search/', options);
    const data =  await response.json();
    return data;
}

const addMemories = async (messages: LanguageModelV1Prompt, config?: Mem0ConfigSettings)=>{
    let finalMessages: Array<Message> = [];
    if (typeof messages === "string") {
        finalMessages = [{ role: "user", content: messages }];
    }else {
      finalMessages = convertToMem0Format(messages);
    }
    const response = await updateMemories(finalMessages, config);
    return response;
}

const updateMemories = async (messages: Array<Message>, config?: Mem0ConfigSettings)=>{
    const options = {
        method: 'POST',
        headers: {Authorization: `Token ${loadApiKey({
            apiKey: (config&&config.mem0ApiKey),
            environmentVariableName: "MEM0_API_KEY",
            description: "Mem0",
        })}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({messages, ...config}),
    };

    const response  = await fetch('https://api.mem0.ai/v1/memories/', options);
    const data =  await response.json();
    return data;
}

const retrieveMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0ConfigSettings)=>{
    const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
    const systemPrompt = "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n";
    const memories = await searchInternalMemories(message, config);
    let memoriesText1 = "";
    let memoriesText2 = "";
    let graphPrompt = "";
    try{
        // @ts-ignore
        memoriesText1 = memories.results.map((memory: any)=>{
            return `Memory: ${memory.memory}\n\n`;
        }).join("\n\n");

        if (config?.enable_graph) {
            memoriesText2 = memories.relations.map((memory: any)=>{
                return `Relation: ${memory.source} -> ${memory.relationship} -> ${memory.target} \n\n`;
            }).join("\n\n");
        }

        if (config?.enable_graph) {
            graphPrompt = `HERE ARE THE GRAPHS RELATIONS FOR THE PREFERENCES OF THE USER:\n\n ${memoriesText2}`;
        }
    }catch(e){
        console.error("Error while parsing memories");
        // console.log(e);
    }
    if(memories.length === 0){
      return "";
    }
    return `System Message: ${systemPrompt} ${memoriesText1} ${graphPrompt}`;
}

const getMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0ConfigSettings)=>{
    const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
    let memories = [];
    try{
        // @ts-ignore
        memories = await searchInternalMemories(message, config);
        if (!config?.enable_graph) {
            memories = memories.results;
        }
    }
    catch(e){
        console.error("Error while searching memories");
    }
    return memories;
}

const searchMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0ConfigSettings)=>{
    const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
    let memories = [];
    try{
        // @ts-ignore
        memories = await searchInternalMemories(message, config);
    }
    catch(e){
        console.error("Error while searching memories");
    }
    return memories;
}

export {addMemories, updateMemories, retrieveMemories, flattenPrompt, searchMemories, getMemories};