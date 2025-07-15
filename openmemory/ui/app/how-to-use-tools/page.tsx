"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Code, BotMessageSquare, BrainCircuit, Search, List, Wand2, ArrowRight, Lightbulb, FileText } from "lucide-react";
import { motion } from "framer-motion";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { Badge } from "@/components/ui/badge";
import { RequestFeatureModal } from "@/components/tools/RequestFeatureModal";
import { ProtectedRoute } from "@/components/ProtectedRoute";

const tools = [
  {
    name: "jean_memory",
    icon: <BrainCircuit className="w-6 h-6 text-purple-500" />,
    description: "🌟 THE PRIMARY TOOL - Intelligent context engineering that automatically adapts. For new conversations, provides deep comprehensive understanding. For follow-ups, gives targeted fast responses. Always use this tool first.",
    example: "jean_memory: 'Hi! I'm testing the new smart context system.' (is_new_conversation: true)",
    badge: "Primary Tool",
    isNew: true
  },
  {
    name: "ask_memory",
    icon: <BrainCircuit className="w-6 h-6 text-primary" />,
    description: "Fast memory search for simple questions about your memories, thoughts, and experiences.",
    example: "ask_memory: 'What are my main interests and preferences?'"
  },
  {
    name: "search_memory",
    icon: <Search className="w-6 h-6 text-primary" />,
    description: "Quick keyword-based search through your memories for specific information.",
    example: "search_memory: 'Q3 project goals'"
  },
  {
    name: "add_memories",
    icon: <BotMessageSquare className="w-6 h-6 text-primary" />,
    description: "Manually store specific information (jean_memory handles this automatically in most cases).",
    example: "add_memories: 'I met with John Doe today to discuss the Q3 project goals.'"
  },
  {
    name: "store_document",
    icon: <FileText className="w-6 h-6 text-primary" />,
    description: "Store large documents like files, articles, or notes. Creates a searchable summary automatically.",
    example: 'store_document: { title: "Meeting Notes Q3", content: "..." }',
  },
  {
    name: "list_memories",
    icon: <List className="w-6 h-6 text-primary" />,
    description: "Browse through your stored memories to get an overview.",
    example: "list_memories"
  },
];

const deepMemoryTool = {
  name: "deep_memory_query",
  icon: <Wand2 className="w-6 h-6 text-purple-400" />,
  description: "Advanced standalone tool for complex analysis over your entire memory bank. Note: This capability is now automatically built into jean_memory for new conversations and rich content.",
  examples: [
    "\"Tell me everything about Jonathan - his personality, work, interests, values\"",
    "\"Analyze my recent thoughts and tell me about patterns I might not be aware of\"",
    "\"What are the key themes across all my stored experiences?\"",
  ]
};

export default function HowToUsePage() {
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);

  return (
    <ProtectedRoute>
      <div className="relative min-h-screen w-full bg-background">
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="how-to-use-particles" className="h-full w-full" interactive={false} particleCount={80} />
      </div>
      <div className="absolute inset-0 bg-gradient-to-b from-background/30 via-background/80 to-background z-5" />
      
      <div className="relative z-10 container mx-auto px-4 py-16 max-w-4xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">
            Using Your Memory Tools
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
            Jean Memory now features intelligent context engineering. <strong>jean_memory</strong> is your primary tool that automatically provides deep understanding for new conversations and fast responses for follow-ups.
          </p>
        </motion.div>

        <div className="space-y-6">
          {tools.map((tool, index) => (
            <motion.div
              key={tool.name}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.1 * (index + 1) }}
            >
              <Card className="bg-card/50 hover:bg-card/80 transition-colors duration-300">
                <CardHeader>
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-secondary rounded-lg">{tool.icon}</div>
                    <div className="flex-1">
                      <CardTitle className="flex items-center gap-2 font-mono text-lg">
                        {tool.name}
                        {tool.badge && (
                          <Badge variant="secondary" className="bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                            {tool.badge}
                          </Badge>
                        )}
                        {tool.isNew && (
                          <Badge variant="default" className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                            Enhanced
                          </Badge>
                        )}
                      </CardTitle>
                      <p className="text-sm text-muted-foreground mt-1">{tool.description}</p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="p-3 rounded-md bg-secondary text-sm text-secondary-foreground overflow-x-auto">
                    <code>{tool.example}</code>
                  </pre>
                </CardContent>
              </Card>
            </motion.div>
          ))}
          
          {/* Smart Behavior Explanation */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <Card className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/50 dark:to-blue-950/50 border border-purple-200 dark:border-purple-500/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <BrainCircuit className="w-6 h-6 text-purple-500" />
                  How jean_memory Automatically Adapts
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid gap-3">
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-purple-500 rounded-full mt-2 flex-shrink-0"></div>
                      <div>
                        <p className="font-semibold text-sm">New Conversations</p>
                        <p className="text-sm text-muted-foreground">Automatically provides deep, comprehensive understanding (30-60s) to establish rich context</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                      <div>
                        <p className="font-semibold text-sm">Rich Personal Content</p>
                        <p className="text-sm text-muted-foreground">Detects when you share substantial personal information and triggers deep analysis</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                      <div>
                        <p className="font-semibold text-sm">Follow-up Questions</p>
                        <p className="text-sm text-muted-foreground">Fast, targeted responses (5-10s) for continuing conversations</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-2 h-2 bg-amber-500 rounded-full mt-2 flex-shrink-0"></div>
                      <div>
                        <p className="font-semibold text-sm">Explicit Deep Requests</p>
                        <p className="text-sm text-muted-foreground">Triggers comprehensive analysis when you ask to "go deeper" or "tell me everything"</p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
          
          {/* Deep Memory Query Card */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.7 }}
          >
            <Card className="bg-card/50 border border-purple-200 dark:border-purple-500/30 hover:border-purple-400/50 dark:hover:border-purple-500/50 transition-colors duration-300">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/50 rounded-lg">{deepMemoryTool.icon}</div>
                  <div>
                    <CardTitle className="flex items-center gap-2 font-mono text-lg">
                      {deepMemoryTool.name}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">{deepMemoryTool.description}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-muted-foreground">Example Use Cases:</h4>
                  {deepMemoryTool.examples.map((example, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <ArrowRight className="w-4 h-4 text-purple-500 dark:text-purple-400 flex-shrink-0" />
                      <span className="font-mono text-secondary-foreground">{example}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Request Feature Card */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.8 }}
            onClick={() => setIsRequestModalOpen(true)}
            className="cursor-pointer"
          >
            <Card className="bg-card/50 hover:bg-card/80 transition-colors duration-300">
              <CardHeader>
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-secondary rounded-lg">
                    <Lightbulb className="w-6 h-6 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      Request a Tool or Feature
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      Have an idea for a new tool or an improvement? Let us know!
                    </p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-muted-foreground ml-auto" />
                </div>
              </CardHeader>
            </Card>
          </motion.div>
        </div>
      </div>
      <RequestFeatureModal
        open={isRequestModalOpen}
        onOpenChange={setIsRequestModalOpen}
      />
    </div>
    </ProtectedRoute>
  );
} 