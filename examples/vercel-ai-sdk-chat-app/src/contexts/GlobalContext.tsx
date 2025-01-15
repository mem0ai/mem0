/* eslint-disable @typescript-eslint/no-explicit-any */
import { createContext, useEffect, useState } from "react";
import { createMem0, searchMemories } from "@mem0/vercel-ai-provider";
import { LanguageModelV1Prompt, streamText } from "ai";
import { Message, Memory, FileInfo } from "@/types";
import { Buffer } from 'buffer';

const GlobalContext = createContext<any>({});

const WelcomeMessage: Message = {
  id: "1",
  content:
    "👋 Hi there! I'm your personal assistant. How can I help you today? 😊",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

const InvalidConfigMessage: Message = {
  id: "2",
  content:
    "Invalid configuration. Please check your API keys, and add a user and try again.",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

const SomethingWentWrongMessage: Message = {
  id: "3",
  content: "Something went wrong. Please try again.",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

const models = {
  "openai": "gpt-4o",
  "anthropic": "claude-3-haiku-20240307",
  "cohere": "command-r-plus",
  "groq": "gemma2-9b-it"
}

const getModel = (provider: string) => {
  switch (provider) {
    case "openai":
      return models.openai;
    case "anthropic":
      return models.anthropic;
    case "cohere":
      return models.cohere;
    case "groq":
      return models.groq;
    default:
      return models.openai;
  }
}

const GlobalState = (props: any) => {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [thinking, setThinking] = useState<boolean>(false);
  const [selectedOpenAIKey, setSelectedOpenAIKey] = useState<string>("");
  const [selectedMem0Key, setSelectedMem0Key] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("openai");
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null)
  const [file, setFile] = useState<any>(null)

  const mem0 = createMem0({
    provider: selectedProvider,
    mem0ApiKey: selectedMem0Key,
    apiKey: selectedOpenAIKey,
  });

  const clearConfiguration = () => {
    localStorage.removeItem("mem0ApiKey");
    localStorage.removeItem("openaiApiKey");
    localStorage.removeItem("provider");
    setSelectedMem0Key("");
    setSelectedOpenAIKey("");
    setSelectedProvider("openai");
    setSelectedUser("");
    setMessages([WelcomeMessage]);
    setMemories([]);
    setFile(null);
  };

  const selectorHandler = (mem0: string, openai: string, provider: string) => {
    setSelectedMem0Key(mem0);
    setSelectedOpenAIKey(openai);
    setSelectedProvider(provider);
    localStorage.setItem("mem0ApiKey", mem0);
    localStorage.setItem("openaiApiKey", openai);
    localStorage.setItem("provider", provider);
  };


  useEffect(() => {
    const mem0 = localStorage.getItem("mem0ApiKey");
    const openai = localStorage.getItem("openaiApiKey");
    const provider = localStorage.getItem("provider");
    const user = localStorage.getItem("user");
    if (mem0 && openai && provider) {
      selectorHandler(mem0, openai, provider);
    }
    if (user) {
      setSelectedUser(user);
    }
  }, []);

  const selectUserHandler = (user: string) => {
    setSelectedUser(user);
    localStorage.setItem("user", user);
  };

  const clearUserHandler = () => {
    setSelectedUser("");
    setMemories([]);
  };

  const getMemories = async (messages: LanguageModelV1Prompt) => {
    try {
      const smemories = await searchMemories(messages, {
        user_id: selectedUser || "",
        mem0ApiKey: selectedMem0Key,
      });

      const newMemories = smemories.map((memory: any) => ({
        id: memory.id,
        content: memory.memory,
        timestamp: memory.updated_at,
        tags: memory.categories,
      }));
      setMemories(newMemories);
    } catch (error) {
      console.error("Error in getMemories:", error);
    }
  };

  const handleSend = async (inputValue: string) => {
    if (!inputValue.trim() && !file) return;
    if (!selectedUser) {
      const newMessage: Message = {
        id: Date.now().toString(),
        content: inputValue,
        sender: "user",
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, newMessage, InvalidConfigMessage]);
      return;
    }   

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: "user",
      timestamp: new Date().toLocaleTimeString(),
    };

    let fileData;
    if (file) {
      if (file.type.startsWith("image/")) {
        // Convert image to Base64
        fileData = await convertToBase64(file);
        userMessage.image = fileData;
      } else if (file.type.startsWith("audio/")) {
        // Convert audio to ArrayBuffer
        fileData = await getFileBuffer(file);
        userMessage.audio = fileData;
      }
    }

    // Update the state with the new user message
    setMessages((prev) => [...prev, userMessage]);
    setThinking(true);

    // Transform messages into the required format
    const messagesForPrompt: LanguageModelV1Prompt = [];
    messages.map((message) => {
      const messageContent: any = {
        role: message.sender,
        content: [
          {
            type: "text",
            text: message.content,
          },
        ],
      };
      if (message.image) {
        messageContent.content.push({
          type: "image",
          image: message.image,
        });
      }
      if (message.audio) {
        messageContent.content.push({
          type: 'file',
          mimeType: 'audio/mpeg',
          data: message.audio,
        });
      }
      if(!message.audio) messagesForPrompt.push(messageContent);
    });

    const newMessage: any = {
      role: "user",
      content: [
        {
          type: "text",
          text: inputValue,
        },
      ],
    };
    if (file) {
      if (file.type.startsWith("image/")) {
        newMessage.content.push({
          type: "image",
          image: userMessage.image,
        });
      } else if (file.type.startsWith("audio/")) {
        newMessage.content.push({
          type: 'file',
          mimeType: 'audio/mpeg',
          data: userMessage.audio,
        });
      }
    }

    messagesForPrompt.push(newMessage);
    getMemories(messagesForPrompt);

    setFile(null);
    setSelectedFile(null);

    try {
      const { textStream } = await streamText({
        model: mem0(getModel(selectedProvider), {
          user_id: selectedUser || "",
        }),
        messages: messagesForPrompt,
      });

      const assistantMessageId = Date.now() + 1;
      const assistantMessage: Message = {
        id: assistantMessageId.toString(),
        content: "",
        sender: "assistant",
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Stream the text part by part
      for await (const textPart of textStream) {
        assistantMessage.content += textPart;
        setThinking(false);
        setFile(null);
        setSelectedFile(null);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId.toString()
              ? { ...msg, content: assistantMessage.content }
              : msg
          )
        );
      }

      setThinking(false);
    } catch (error) {
      console.error("Error in handleSend:", error);
      setMessages((prev) => [...prev, SomethingWentWrongMessage]);
      setThinking(false);
      setFile(null);
      setSelectedFile(null);
    }
  };

  useEffect(() => {
    setMessages([WelcomeMessage]);
  }, []);

  return (
    <GlobalContext.Provider
      value={{
        selectedUser,
        selectUserHandler,
        clearUserHandler,
        messages,
        memories,
        handleSend,
        thinking,
        selectedMem0Key,
        selectedOpenAIKey,
        selectedProvider,
        selectorHandler,
        clearConfiguration,
        selectedFile,
        setSelectedFile,
        file,
        setFile
      }}
    >
      {props.children}
    </GlobalContext.Provider>
  );
};

export default GlobalContext;
export { GlobalState };


const convertToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => resolve(reader.result as string); // Resolve with Base64 string
      reader.onerror = error => reject(error); // Reject on error
  });
};

async function getFileBuffer(file: any) {
  const response = await fetch(file);
  const arrayBuffer = await response.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  return buffer;
}