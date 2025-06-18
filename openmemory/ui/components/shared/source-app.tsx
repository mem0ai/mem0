import React from "react";
import { BiEdit } from "react-icons/bi";
import Image from "next/image";

export const Icon = ({ source }: { source: string }) => {
  return (
    <div className="w-4 h-4 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden -mr-1">
      <Image src={source} alt={source} width={40} height={40} />
    </div>
  );
};

export const constants = {
  'request-integration': {
    name: "Request Integration",
    icon: <div className="w-4 h-4 rounded-full bg-zinc-700 flex items-center justify-center text-white text-xs font-bold">+</div>,
    iconImage: null,
  },
  chatgpt: {
    name: "ChatGPT",
    icon: <Icon source="/images/ChatGPT-Logo.svg" />,
    iconImage: "/images/ChatGPT-Logo.svg",
  },
  claude: {
    name: "Claude",
    icon: <Icon source="/images/claude.webp" />,
    iconImage: "/images/claude.webp",
  },
  openmemory: {
    name: "Jean Memory",
    icon: <Icon source="/images/open-memory.svg" />,
    iconImage: "/images/open-memory.svg",
  },
  "jean memory": {
    name: "Jean Memory",
    icon: <Icon source="/images/jean-bug.png" />,
    iconImage: "/images/jean-bug.png",
  },
  cursor: {
    name: "Cursor",
    icon: <Icon source="/images/cursor.png" />,
    iconImage: "/images/cursor.png",
  },
  cline: {
    name: "Cline",
    icon: <Icon source="/images/cline.png" />,
    iconImage: "/images/cline.png",
  },
  roocode: {
    name: "Roo Code",
    icon: <Icon source="/images/roocline.png" />,
    iconImage: "/images/roocline.png",
  },
  windsurf: {
    name: "Windsurf",
    icon: <Icon source="/images/windsurf.png" />,
    iconImage: "/images/windsurf.png",
  },
  witsy: {
    name: "Witsy",
    icon: <Icon source="/images/witsy.png" />,
    iconImage: "/images/witsy.png",
  },
  enconvo: {
    name: "Enconvo",
    icon: <Icon source="/images/enconvo.png" />,
    iconImage: "/images/enconvo.png",
  },
  substack: {
    name: "Substack",
    icon: <Icon source="/images/substack.png" />,
    iconImage: "/images/substack.png",
  },
  twitter: {
    name: "X",
    icon: <Icon source="/images/x.svg" />,
    iconImage: "/images/x.svg",
  },
  notion: {
    name: "Notion",
    icon: <Icon source="/images/notion.svg" />,
    iconImage: "/images/notion.svg",
  },
  obsidian: {
    name: "Obsidian",
    icon: <Icon source="/images/obsidian.svg" />,
    iconImage: "/images/obsidian.svg",
  },
  default: {
    name: "Default",
    icon: <BiEdit size={18} className="ml-1" />,
    iconImage: "/images/default.png",
  },
};

const SourceApp = ({ source }: { source: string }) => {
  // Normalize the source string to handle variations
  const normalizedSource = source?.toLowerCase().trim();
  
  // Create a mapping for normalized keys to handle variations
  const sourceMapping: { [key: string]: keyof typeof constants } = {
    'request-integration': 'request-integration',
    'request integration': 'request-integration',
    'chatgpt': 'chatgpt',
    'chat-gpt': 'chatgpt',
    'openai': 'chatgpt',
    'twitter': 'twitter',
    'x': 'twitter',
    'substack': 'substack',
    'claude': 'claude',
    'openmemory': 'openmemory',
    'jean memory': 'jean memory',
    'cursor': 'cursor',
    'cline': 'cline',
    'roocode': 'roocode',
    'windsurf': 'windsurf',
    'witsy': 'witsy',
    'enconvo': 'enconvo',
    'notion': 'notion',
    'obsidian': 'obsidian'
  };
  
  // Find the correct constant key
  const constantKey = sourceMapping[normalizedSource] || normalizedSource as keyof typeof constants;
  const appConfig = constants[constantKey];
  
  if (!appConfig) {
    return (
      <div className="flex items-center gap-2">
        <BiEdit size={16} />
        <span className="text-sm font-semibold">{source}</span>
      </div>
    );
  }
  
  return (
    <div className="flex items-center gap-2">
      {appConfig.icon}
      <span className="text-sm font-semibold">
        {appConfig.name}
      </span>
    </div>
  );
};

export default SourceApp;
