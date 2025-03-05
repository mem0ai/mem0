"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import { useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { Sun, Moon, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import ThemeAwareLogo from "@/components/mem0/theme-aware-logo";
import Link from "next/link";
import GithubButton from "@/components/mem0/github-button";

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

  const resetUserId = () => {
    const newId = uuidv4();
    localStorage.setItem("userId", newId);
    setUserId(newId);
    // Clear all threads from localStorage
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith('thread:')) {
        localStorage.removeItem(key);
      }
    });
    // Force reload to clear all states
    window.location.reload();
  };

  return { userId, resetUserId };
};

export const Assistant = () => {
  const { userId, resetUserId } = useUserId();
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
      <div className={`h-dvh bg-[#f8fafc] dark:bg-zinc-900 text-[#1e293b] ${isDarkMode ? "dark" : ""}`}>
        <header className="h-16 border-b border-[#e2e8f0] flex items-center justify-between px-4 sm:px-6 bg-white dark:bg-zinc-900 dark:border-zinc-800 dark:text-white">
          <div className="flex items-center">
          <Link href="/" className="flex items-center">
            <ThemeAwareLogo width={120} height={40} isDarkMode={isDarkMode} />
          </Link>
          </div>

          <div className="flex items-center">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => setSidebarOpen(true)}
              className="text-[#475569] dark:text-zinc-300 md:hidden"
            >
              <MessageSquare className="w-10 h-10" />
            </Button>
            <button
              className="p-2 rounded-full hover:bg-[#eef2ff] dark:hover:bg-zinc-800 text-[#475569] dark:text-zinc-300"
              onClick={toggleDarkMode}
              aria-label="Toggle theme"
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <GithubButton url="https://github.com/mem0ai/mem0/tree/main/examples" />
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-x-0 h-[calc(100vh-8rem)] md:h-[calc(100vh-4rem)]">
          <ThreadList onResetUserId={resetUserId} isDarkMode={isDarkMode} />
          <Thread sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} onResetUserId={resetUserId} isDarkMode={isDarkMode} />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
};
