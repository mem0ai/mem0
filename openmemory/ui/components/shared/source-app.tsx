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
  claude: {
    name: "Claude",
    icon: <Icon source="/images/claude.webp" />,
    iconImage: "/images/claude.webp",
  },
  openmemory: {
    name: "OpenMemory",
    icon: <Icon source="/images/open-memory.svg" />,
    iconImage: "/images/open-memory.svg",
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
  roocline: {
    name: "Roo Cline",
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
  default: {
    name: "Default",
    icon: <BiEdit size={18} className="ml-1" />,
    iconImage: "/images/default.png",
  },
};

const SourceApp = ({ source }: { source: string }) => {
  if (!constants[source as keyof typeof constants]) {
    return (
      <div>
        <BiEdit />
        <span className="text-sm font-semibold">{source}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2">
      {constants[source as keyof typeof constants].icon}
      <span className="text-sm font-semibold">
        {constants[source as keyof typeof constants].name}
      </span>
    </div>
  );
};

export default SourceApp;
