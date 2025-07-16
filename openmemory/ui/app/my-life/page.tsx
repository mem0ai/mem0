"use client";

import { useState } from "react";
import KnowledgeGraph from "./components/KnowledgeGraph";
import InteractiveExplorer from "./components/InteractiveExplorer";
import AdvancedKnowledgeGraph from "./components/AdvancedKnowledgeGraph";
// import ChatInterface from "./components/ChatInterface";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { MessageSquare, Network, Map, RotateCcw, Sparkles } from "lucide-react";
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
  const [viewMode, setViewMode] = useState<"explorer" | "graph" | "advanced">("explorer");
  const [isChatOpen, setIsChatOpen] = useState(true);

  return (
    <ProtectedRoute>
      <div className="h-[calc(100vh-3.5rem)] lg:h-[calc(100vh-3.5rem)] flex bg-background text-foreground">
      
      {/* Vertical Sidebar for View Mode Toggle */}
      <div className="hidden lg:flex flex-col w-24 bg-card border-r border-border">
        <div className="flex flex-col gap-2 p-3">
          <Button
            variant={viewMode === "explorer" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("explorer")}
            className="flex flex-col items-center gap-1 h-14 w-18"
            title="Explorer"
          >
            <Map className="h-5 w-5" />
            <span className="text-xs">Explorer</span>
          </Button>
          <Button
            variant={viewMode === "advanced" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("advanced")}
            className="flex flex-col items-center gap-1 h-14 w-18"
            title="Advanced Graph"
          >
            <Sparkles className="h-5 w-5" />
            <span className="text-xs">Graph</span>
          </Button>
          {/* 3D Graph tab - hidden for now but keeping code for later use
          <Button
            variant={viewMode === "graph" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("graph")}
            className="flex flex-col items-center gap-1 h-14 w-18"
            title="3D Graph"
          >
            <Network className="h-5 w-5" />
            <span className="text-xs">3D Graph</span>
          </Button>
          */}
        </div>
      </div>

      {/* Mobile View Toggle */}
      <div className="lg:hidden flex flex-col w-full">
        <div className="flex items-center justify-center gap-2 p-2 bg-card border-b border-border">
          <Button
            variant={viewMode === "explorer" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("explorer")}
            className="flex items-center gap-2"
          >
            <Map className="h-4 w-4" />
            Explorer
          </Button>
          <Button
            variant={viewMode === "advanced" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("advanced")}
            className="flex items-center gap-2"
          >
            <Sparkles className="h-4 w-4" />
            Graph
          </Button>
          {/* 3D Graph tab - hidden for now but keeping code for later use
          <Button
            variant={viewMode === "graph" ? "default" : "ghost"}
            size="sm"
            onClick={() => setViewMode("graph")}
            className="flex items-center gap-2"
          >
            <Network className="h-4 w-4" />
            3D Graph
          </Button>
          */}
        </div>
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

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Main Content Section */}
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="flex-1 relative overflow-hidden"
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
        
        {viewMode === "advanced" && (
          <AdvancedKnowledgeGraph onMemorySelect={setSelectedMemory} />
        )}
        </motion.div>
      </div>

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