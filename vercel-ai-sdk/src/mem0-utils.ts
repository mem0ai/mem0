import { LanguageModelV1Prompt } from 'ai';
import { Mem0Config } from './mem0-chat-settings';
if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV !== 'production') {
    // Dynamically import dotenv only in non-production environments
    import('dotenv').then((dotenv) => dotenv.config());
}

const tokenIsPresent = (config?: Mem0Config)=>{
    if(!config && !config!.mem0ApiKey && (typeof process !== 'undefined' && process.env && !process.env.MEM0_API_KEY)){
        throw Error("MEM0_API_KEY is not present. Please set env MEM0_API_KEY as the value of your API KEY.");
    }
}

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

function convertMessagesToMem0Format(messages: LanguageModelV1Prompt) {
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

const searchInternalMemories = async (query: string, config?: Mem0Config, top_k: number = 5)=> {
    tokenIsPresent(config);
    const filters = {
      OR: [
        {
          user_id: config&&config.user_id,
        },
        {
          app_id: config&&config.app_id,
        },
        {
          agent_id: config&&config.agent_id,
        },
        {
          run_id: config&&config.run_id,
        },
      ],
    };
    const org_project_filters = {
      org_id: config&&config.org_id,
      project_id: config&&config.project_id,
      org_name: !config?.org_id ? config&&config.org_name : undefined,  // deprecated
      project_name: !config?.org_id ? config&&config.project_name : undefined, // deprecated
    }
    const options = {
        method: 'POST',
        headers: {Authorization: `Token ${(config&&config.mem0ApiKey) || (typeof process !== 'undefined' && process.env && process.env.MEM0_API_KEY) || ""}`, 'Content-Type': 'application/json'}, 
        body: JSON.stringify({query, filters, top_k, version: "v2", ...org_project_filters}),
    };
    const response  = await fetch('https://api.mem0.ai/v2/memories/search/', options);
    const data =  await response.json();
    return data;
}

const addMemories = async (messages: LanguageModelV1Prompt, config?: Mem0Config)=>{
    tokenIsPresent(config);
    const message = flattenPrompt(messages);
    const response = await updateMemories([
        { role: "user", content: message },
        { role: "assistant", content: "Thank You!" },
    ], config);
    return response;
}

const updateMemories = async (messages: Array<Message>, config?: Mem0Config)=>{
    tokenIsPresent(config);
    const options = {
        method: 'POST',
        headers: {Authorization: `Token ${(config&&config.mem0ApiKey) || (typeof process !== 'undefined' && process.env && process.env.MEM0_API_KEY) || ""}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({messages, ...config}),
    };

    const response  = await fetch('https://api.mem0.ai/v1/memories/', options);
    const data =  await response.json();
    return data;
}

const retrieveMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0Config)=>{
    tokenIsPresent(config);
    const message = typeof prompt === 'string' ? prompt : flattenPrompt(prompt);
    const systemPrompt = "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n";
    const memories = await searchInternalMemories(message, config);
    let memoriesText = "";
    try{
        // @ts-ignore
        memoriesText = memories.map((memory: any)=>{
            return `Memory: ${memory.memory}\n\n`;
        }).join("\n\n");
    }catch(e){
        console.error("Error while parsing memories");
        // console.log(e);
    }
    if(memories.length === 0){
      return "";
    }
    return `System Message: ${systemPrompt} ${memoriesText}`;
}

const getMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0Config)=>{
    tokenIsPresent(config);
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

const searchMemories = async (prompt: LanguageModelV1Prompt | string, config?: Mem0Config)=>{
    tokenIsPresent(config);
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

export {addMemories, updateMemories, retrieveMemories, flattenPrompt, searchMemories, convertMessagesToMem0Format, getMemories};