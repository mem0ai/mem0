"use client";

import { useState } from "react";
import KnowledgeGraph from "./components/KnowledgeGraph";
import InteractiveExplorer from "./components/InteractiveExplorer";
// import ChatInterface from "./components/ChatInterface";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { MessageSquare, Network, Map, RotateCcw } from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
/*
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
*/

export default function MyLifePage() {
  const [selectedMemory, setSelectedMemory] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"graph" | "chat">("graph");
  const [viewMode, setViewMode] = useState<"explorer" | "graph">("explorer");
  const [isChatOpen, setIsChatOpen] = useState(true);

  return (
    <ProtectedRoute>
      <div className="h-[calc(100vh-3.5rem)] lg:h-[calc(100vh-3.5rem)] flex flex-col lg:flex-row bg-background text-foreground">
      {/* View Mode Toggle */}
      <div className="flex items-center justify-between gap-2 p-2 bg-card border-b border-border">
        {/* Mobile View Toggle (left side) */}
        <div className="lg:hidden flex items-center gap-2">
          <Button
            variant={mobileView === "graph" ? "default" : "ghost"}
            size="sm"
            onClick={() => setMobileView("graph")}
            className="flex items-center gap-2"
          >
            {viewMode === "explorer" ? <Map className="h-4 w-4" /> : <Network className="h-4 w-4" />}
            {viewMode === "explorer" ? "Explorer" : "Graph"}
          </Button>
        </div>

        {/* View Mode Toggle (center/right) */}
        <div className="flex items-center gap-2">
          <Button
            variant={viewMode === "explorer" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("explorer")}
            className="flex items-center gap-2"
          >
            <Map className="h-4 w-4" />
            <span className="hidden sm:inline">Explorer</span>
          </Button>
          <Button
            variant={viewMode === "graph" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("graph")}
            className="flex items-center gap-2"
          >
            <Network className="h-4 w-4" />
            <span className="hidden sm:inline">3D Graph</span>
          </Button>
        </div>
        {/*
        <Button
          variant={mobileView === "chat" ? "default" : "ghost"}
          size="sm"
          onClick={() => setMobileView("chat")}
          className="flex items-center gap-2"
        >
          <MessageSquare className="h-4 w-4" />
          Chat
        </Button>
        */}
      </div>

      {/* Main Content Section */}
      <motion.div 
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className={`
          ${mobileView === "graph" ? "flex" : "hidden"} 
          flex-1 relative overflow-hidden 
          lg:border-r border-border
          h-[calc(100vh-7rem)] lg:h-full
          lg:flex
        `}
      >
        {viewMode === "graph" && (
          <>
            <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 via-transparent to-blue-900/10" />
            <KnowledgeGraph onMemorySelect={setSelectedMemory} />
          </>
        )}
        
        {viewMode === "explorer" && (
          <InteractiveExplorer onMemorySelect={setSelectedMemory} />
        )}
      </motion.div>

      {/* Chat Interface Section */}
      {/*
      <div className={`
        ${mobileView === "chat" ? "flex" : "hidden"}
        lg:flex
      `}>
        <Collapsible
          open={isChatOpen}
          onOpenChange={setIsChatOpen}
          className="h-full"
        >
          <CollapsibleContent className="h-full">
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className={`
                flex flex-col bg-card
                w-full lg:w-[400px] xl:w-[500px]
                h-[calc(100vh-7rem)] lg:h-full
              `}
            >
              <ChatInterface selectedMemory={selectedMemory} />
            </motion.div>
          </CollapsibleContent>
          <div className="hidden lg:flex items-center justify-center p-2 h-full border-l border-border bg-background">
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MessageSquare className={`h-4 w-4 transition-transform duration-300 ${isChatOpen ? 'rotate-90' : ''}`} />
                </Button>
              </CollapsibleTrigger>
          </div>
        </Collapsible>
      </div>
      */}
    </div>
    </ProtectedRoute>
  );
} 