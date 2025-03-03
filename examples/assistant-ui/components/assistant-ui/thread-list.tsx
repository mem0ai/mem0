import type { FC } from "react";
import {
  ThreadListItemPrimitive,
  ThreadListPrimitive,
} from "@assistant-ui/react";
import { ArchiveIcon, PlusIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";

export const ThreadList: FC = () => {
  return (
    <div className="flex-col h-full border-r border-[#e2e8f0] bg-white dark:bg-zinc-900 dark:border-zinc-800 p-3 overflow-y-auto hidden md:flex">
      <ThreadListPrimitive.Root className="flex flex-col items-stretch gap-1.5">
        <ThreadListNew />
        <div className="mt-4 mb-2">
          <h2 className="text-sm font-medium text-[#475569] dark:text-zinc-300 px-2.5">Recent Chats</h2>
        </div>
        <ThreadListItems />
      </ThreadListPrimitive.Root>
    </div>
  );
};

const ThreadListNew: FC = () => {
  return (
    <ThreadListPrimitive.New asChild>
      <Button
        className="hover:bg-[#8ea4e8] dark:hover:bg-zinc-800 dark:data-[active]:bg-zinc-800 flex items-center justify-start gap-1 rounded-lg px-2.5 py-2 text-start bg-[#4f46e5] text-white dark:bg-[#6366f1]"
        variant="default"
      >
        <PlusIcon className="w-4 h-4" />
        New Thread
      </Button>
    </ThreadListPrimitive.New>
  );
};

const ThreadListItems: FC = () => {
  return <ThreadListPrimitive.Items components={{ ThreadListItem }} />;
};

const ThreadListItem: FC = () => {
  return (
    <ThreadListItemPrimitive.Root className="data-[active]:bg-[#eef2ff] hover:bg-[#eef2ff] dark:hover:bg-zinc-800 dark:data-[active]:bg-zinc-800 dark:text-white focus-visible:bg-[#eef2ff] dark:focus-visible:bg-zinc-800 focus-visible:ring-[#4f46e5] flex items-center gap-2 rounded-lg transition-all focus-visible:outline-none focus-visible:ring-2">
      <ThreadListItemPrimitive.Trigger className="flex-grow px-3 py-2 text-start">
        <ThreadListItemTitle />
      </ThreadListItemPrimitive.Trigger>
      <ThreadListItemArchive />
    </ThreadListItemPrimitive.Root>
  );
};

const ThreadListItemTitle: FC = () => {
  return (
    <p className="text-sm">
      <ThreadListItemPrimitive.Title fallback="New Chat" />
    </p>
  );
};

const ThreadListItemArchive: FC = () => {
  return (
    <ThreadListItemPrimitive.Archive asChild>
      <TooltipIconButton
        className="hover:text-[#4f46e5] text-[#475569] dark:text-zinc-300 dark:hover:text-[#6366f1] ml-auto mr-3 size-4 p-0"
        variant="ghost"
        tooltip="Archive thread"
      >
        <ArchiveIcon />
      </TooltipIconButton>
    </ThreadListItemPrimitive.Archive>
  );
};
