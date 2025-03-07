/* eslint-disable @typescript-eslint/no-explicit-any */
export interface Memory {
  id: string;
  content: string;
  timestamp: string;
  tags: string[];
}

export interface Message {
  id: string;
  content: string;
  sender: "user" | "assistant";
  timestamp: string;
  image?: string;
  audio?: any;
}

export interface FileInfo {
  name: string;
  type: string;
  size: number;
}