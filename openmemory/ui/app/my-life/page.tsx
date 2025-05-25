"use client";

import { useState } from "react";
import KnowledgeGraph from "./components/KnowledgeGraph";
import ChatInterface from "./components/ChatInterface";
import { motion } from "framer-motion";

export default function MyLifePage() {
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null);

  return (
    <div className="h-[calc(100vh-64px)] flex bg-zinc-950">
      {/* Knowledge Graph Section */}
      <motion.div 
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="flex-1 relative overflow-hidden border-r border-zinc-800"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 via-transparent to-blue-900/10" />
        <KnowledgeGraph onMemorySelect={setSelectedMemory} />
      </motion.div>

      {/* Chat Interface Section */}
      <motion.div 
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="w-[500px] flex flex-col bg-zinc-900/50"
      >
        <ChatInterface selectedMemory={selectedMemory} />
      </motion.div>
    </div>
  );
} 