"use client";

import { useState, useEffect } from "react";
import KnowledgeGraph from "./components/KnowledgeGraph";
import ChatInterface from "./components/ChatInterface";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { MessageSquare, Network } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function MyLifePage() {
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"graph" | "chat">("graph");
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // Redirect unauthenticated users
  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth');
    }
  }, [user, isLoading, router]);

  // Show loading while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  // Don't render if user is not authenticated
  if (!user) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-white">Redirecting to login...</div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] lg:h-[calc(100vh-3.5rem)] flex flex-col lg:flex-row bg-zinc-950">
      {/* Mobile Toggle */}
      <div className="lg:hidden flex items-center justify-center gap-2 p-2 bg-zinc-900 border-b border-zinc-800">
        <Button
          variant={mobileView === "graph" ? "default" : "ghost"}
          size="sm"
          onClick={() => setMobileView("graph")}
          className="flex items-center gap-2"
        >
          <Network className="h-4 w-4" />
          Graph
        </Button>
        <Button
          variant={mobileView === "chat" ? "default" : "ghost"}
          size="sm"
          onClick={() => setMobileView("chat")}
          className="flex items-center gap-2"
        >
          <MessageSquare className="h-4 w-4" />
          Chat
        </Button>
      </div>

      {/* Knowledge Graph Section */}
      <motion.div 
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className={`
          ${mobileView === "graph" ? "flex" : "hidden"} 
          lg:flex flex-1 relative overflow-hidden 
          lg:border-r border-zinc-800
          h-[calc(100vh-7rem)] lg:h-full
        `}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 via-transparent to-blue-900/10" />
        <KnowledgeGraph onMemorySelect={setSelectedMemory} />
      </motion.div>

      {/* Chat Interface Section */}
      <motion.div 
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className={`
          ${mobileView === "chat" ? "flex" : "hidden"} 
          lg:flex flex-col bg-zinc-900/50
          w-full lg:w-[500px] xl:w-[600px]
          h-[calc(100vh-7rem)] lg:h-full
        `}
      >
        <ChatInterface selectedMemory={selectedMemory} />
      </motion.div>
    </div>
  );
} 