import type { FC } from "react";
import {
  ThreadListItemPrimitive,
  ThreadListPrimitive,
} from "@assistant-ui/react";
import { ArchiveIcon, PlusIcon, RefreshCwIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
// import ThemeAwareLogo from "@/components/assistant-ui/theme-aware-logo";
// import Link from "next/link";
interface ThreadListProps {
  onResetUserId?: () => void;
  isDarkMode: boolean;
}

export const ThreadList: FC<ThreadListProps> = ({ onResetUserId }) => {
  const [open, setOpen] = useState(false);
  
  return (
    <div className="flex-col h-full border-r border-[#e2e8f0] bg-white dark:bg-zinc-900 dark:border-zinc-800 p-3 overflow-y-auto hidden md:flex">
      <ThreadListPrimitive.Root className="flex flex-col justify-between h-full items-stretch gap-1.5">
        <div className="flex flex-col h-full items-stretch gap-1.5">
          <ThreadListNew />
          <div className="mt-4 mb-2 flex justify-between items-center px-2.5">
            <h2 className="text-sm font-medium text-[#475569] dark:text-zinc-300">
              Recent Chats
            </h2>
            {onResetUserId && (
              <AlertDialog open={open} onOpenChange={setOpen}>
                <AlertDialogTrigger asChild>
                  <TooltipIconButton
                    tooltip="Reset Memory"
                    className="hover:text-[#4f46e5] text-[#475569] dark:text-zinc-300 dark:hover:text-[#6366f1] size-4 p-0"
                    variant="ghost"
                  >
                    <RefreshCwIcon className="w-4 h-4" />
                  </TooltipIconButton>
                </AlertDialogTrigger>
                <AlertDialogContent className="bg-white dark:bg-zinc-900 border-[#e2e8f0] dark:border-zinc-800">
                  <AlertDialogHeader>
                    <AlertDialogTitle className="text-[#1e293b] dark:text-white">
                      Reset Memory
                    </AlertDialogTitle>
                    <AlertDialogDescription className="text-[#475569] dark:text-zinc-300">
                      This will permanently delete all your chat history and
                      memories. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className="text-[#475569] dark:text-zinc-300 hover:bg-[#eef2ff] dark:hover:bg-zinc-800">
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => {
                        onResetUserId();
                        setOpen(false);
                      }}
                      className="bg-[#4f46e5] hover:bg-[#4338ca] dark:bg-[#6366f1] dark:hover:bg-[#4f46e5] text-white"
                    >
                      Reset
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
          <ThreadListItems />
        </div>

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
