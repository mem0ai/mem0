"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { Sun, Moon, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

const useUserId = () => {
  const [userId, setUserId] = useState<string>("");

  useEffect(() => {
    let id = localStorage.getItem("userId");
    if (!id) {
      id = uuidv4();
      localStorage.setItem("userId", id);
    }
    setUserId(id);
  }, []);

  return userId;
};

export const Assistant = () => {
  const userId = useUserId();
  const runtime = useChatRuntime({
    api: "/api/chat",
    body: { userId },
  });

  const [isDarkMode, setIsDarkMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode);
    if (!isDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className={`h-dvh bg-[#f8fafc] text-[#1e293b] ${isDarkMode ? "dark" : ""}`}>
        <header className="h-16 border-b border-[#e2e8f0] flex items-center justify-between px-4 sm:px-6 bg-white dark:bg-zinc-900 dark:border-zinc-800 dark:text-white">
          <div className="flex items-center">
            <div className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center text-white font-bold mr-2">
              M
            </div>
            <h1 className="text-xl font-bold">Mem0 AssistantUI</h1>
          </div>

          <div className="flex items-center">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setSidebarOpen(true)}
              className="text-[#475569] dark:text-zinc-300 md:hidden"
            >
              <MessageSquare className="w-8 h-8" />
            </Button>
            <button
              className="p-2 rounded-full hover:bg-[#eef2ff] dark:hover:bg-zinc-800 text-[#475569] dark:text-zinc-300"
              onClick={toggleDarkMode}
              aria-label="Toggle theme"
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-x-0 h-[calc(100vh-4rem)]">
          <ThreadList />
          <Thread sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
};
