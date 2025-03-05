"use client";

import * as React from "react";
import { Book } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "../ui/scroll-area";

export type Memory = {
  event: "ADD" | "UPDATE" | "DELETE" | "GET";
  id: string;
  memory: string;
  score: number;
};

interface MemoryIndicatorProps {
  memories: Memory[];
}

export default function MemoryIndicator({ memories }: MemoryIndicatorProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  // Determine the memory state
  const hasAccessed = memories.some((memory) => memory.event === "GET");
  const hasUpdated = memories.some((memory) => memory.event !== "GET");

  let statusText = "";
  let variant: "default" | "secondary" | "outline" = "default";

  if (hasAccessed && hasUpdated) {
    statusText = "Memory accessed and updated";
    variant = "default";
  } else if (hasAccessed) {
    statusText = "Memory accessed";
    variant = "secondary";
  } else if (hasUpdated) {
    statusText = "Memory updated";
    variant = "default";
  }

  if (!statusText) return null;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Badge
          variant={variant}
          className="flex items-center gap-1 cursor-pointer hover:opacity-90 transition-opacity rounded-full bg-zinc-800 hover:bg-zinc-700 dark:bg-[#6366f1] text-white"
          onMouseEnter={() => setIsOpen(true)}
          onMouseLeave={() => setIsOpen(false)}
        >
          <Book className="h-3.5 w-3.5" />
          <span>{statusText}</span>
        </Badge>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 p-4 rounded-xl border-[#e2e8f0] dark:border-zinc-700"
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
      >
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Memories</h4>
          <ScrollArea className="h-[200px]">
            <ul className="text-sm space-y-2 pr-4">
              {memories.map((memory) => (
                <li
                  key={memory.id + memory.event}
                  className="flex items-start gap-2 pb-2 border-b border-[#e2e8f0] dark:border-zinc-700 last:border-0 last:pb-0"
                >
                  <Badge
                    variant={
                      memory.event === "GET"
                        ? "secondary"
                        : memory.event === "ADD"
                        ? "outline"
                        : memory.event === "UPDATE"
                        ? "default"
                        : "destructive"
                    }
                    className="mt-0.5 text-xs shrink-0 rounded-full"
                  >
                    {memory.event === "GET" && "Accessed"}
                    {memory.event === "ADD" && "Created"}
                    {memory.event === "UPDATE" && "Updated"}
                    {memory.event === "DELETE" && "Deleted"}
                  </Badge>
                  <span className="flex-1">{memory.memory}</span>
                  {memory.event === "GET" && (
                    <span className="shrink-0">
                      {Math.round(memory.score * 100)}%
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  );
}
