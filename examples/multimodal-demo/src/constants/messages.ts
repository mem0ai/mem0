import { Message } from "@/types";

export const WELCOME_MESSAGE: Message = {
  id: "1",
  content: "👋 Hi there! I'm your personal assistant. How can I help you today? 😊",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

export const INVALID_CONFIG_MESSAGE: Message = {
  id: "2",
  content: "Invalid configuration. Please check your API keys, and add a user and try again.",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

export const ERROR_MESSAGE: Message = {
  id: "3",
  content: "Something went wrong. Please try again.",
  sender: "assistant",
  timestamp: new Date().toLocaleTimeString(),
};

export const AI_MODELS = {
  openai: "gpt-4o",
  anthropic: "claude-3-haiku-20240307",
  cohere: "command-r-plus",
  groq: "gemma2-9b-it",
} as const;

export type Provider = keyof typeof AI_MODELS; 