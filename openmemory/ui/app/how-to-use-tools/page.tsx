"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Code, BotMessageSquare, BrainCircuit, Search, List, Wand2, ArrowRight, Lightbulb } from "lucide-react";
import { motion } from "framer-motion";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { Badge } from "@/components/ui/badge";
import { RequestFeatureModal } from "@/components/tools/RequestFeatureModal";

const tools = [
  {
    name: "add_memories",
    icon: <BotMessageSquare className="w-6 h-6 text-primary" />,
    description: "Permanently store any new piece of information, thought, or conversation.",
    example: "add_memories: 'I met with John Doe today to discuss the Q3 project goals.'"
  },
  {
    name: "list_memories",
    icon: <List className="w-6 h-6 text-primary" />,
    description: "View a list of your recent memories to get a quick overview.",
    example: "list_memories"
  },
  {
    name: "search_memories",
    icon: <Search className="w-6 h-6 text-primary" />,
    description: "Find specific memories using keywords or semantic search.",
    example: "search_memories: 'Q3 project goals'"
  },
  {
    name: "ask_memories",
    icon: <BrainCircuit className="w-6 h-6 text-primary" />,
    description: "Ask questions in natural language and get synthesized answers from your memory.",
    example: "ask_memories: 'What are the main points from my last meeting with John?'"
  },
];

const deepMemoryTool = {
  name: "deep_memory",
  icon: <Wand2 className="w-6 h-6 text-purple-400" />,
  description: "Run complex queries over your entire memory bank. It can analyze, synthesize, and even create new content based on your stored experiences, beliefs, and knowledge.",
  examples: [
    "\"Write an essay on the future of AI, using my personal beliefs and writing style.\"",
    "\"Pull together everything I've been working on for the last month and summarize it.\"",
    "\"Analyze my recent journal entries and tell me about trends in my mood that I might not be aware of.\"",
  ]
};

export default function HowToUsePage() {
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);

  return (
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
            Your digital memory is powerful. Here's how to interact with it effectively using simple commands.
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
                    <div>
                      <CardTitle className="flex items-center gap-2 font-mono text-lg">
                        {tool.name}
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
          
          {/* Deep Memory Query Card */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
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
            transition={{ duration: 0.5, delay: 0.7 }}
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
  );
} 