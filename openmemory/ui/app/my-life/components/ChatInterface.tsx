"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, User, Bot, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatInterfaceProps {
  selectedMemory: string | null;
}

export default function ChatInterface({ selectedMemory }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isClient, setIsClient] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { memories } = useMemoriesApi();

  // Initialize client-side only
  useEffect(() => {
    setIsClient(true);
    setMessages([
      {
        id: "1",
        role: "assistant",
        content: "Hello! I'm your personal AI assistant powered by Gemini. I have access to all your memories and can help you explore your life's journey. Ask me anything about your experiences, patterns, or insights from your memories.",
        timestamp: new Date()
      }
    ]);
  }, []);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages]);

  useEffect(() => {
    if (selectedMemory) {
      setInput(`Tell me more about this memory: ${selectedMemory}`);
      textareaRef.current?.focus();
    }
  }, [selectedMemory]);

  const callGeminiAPI = async (userMessage: string, memoriesContext: any[]) => {
    try {
      // Prepare context from memories
      const memoryContext = memoriesContext.slice(0, 20).map(m => 
        `Memory: ${m.content} (from ${m.app_name || 'unknown app'} on ${new Date(m.created_at).toLocaleDateString()})`
      ).join('\n');

      const prompt = `You are a personal AI assistant with access to the user's memories. Based on the following memories and the user's question, provide helpful insights about their life patterns, experiences, and growth.

MEMORIES CONTEXT:
${memoryContext}

USER QUESTION: ${userMessage}

Please provide a thoughtful, personalized response based on the user's memories. If the memories don't contain relevant information for the question, acknowledge this and provide general guidance.`;

      const response = await fetch('/api/chat/gemini', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt,
          memories: memoriesContext
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response from Gemini');
      }

      const data = await response.json();
      return data.response || "I'm having trouble processing your request right now. Please try again.";
    } catch (error) {
      console.error('Gemini API error:', error);
      return "I'm currently unable to access my full capabilities. This would normally use Gemini's long context window to analyze all your memories and provide personalized insights about your life patterns, experiences, and growth over time.";
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput("");
    setIsLoading(true);

    try {
      const aiResponse = await callGeminiAPI(currentInput, memories);
      
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: aiResponse,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Life Assistant</h3>
            <p className="text-xs text-zinc-400">Powered by Gemini AI</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`mb-4 flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div className={`flex gap-3 max-w-[80%] ${message.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`p-2 rounded-lg ${
                  message.role === "user" 
                    ? "bg-purple-500" 
                    : "bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-zinc-700"
                }`}>
                  {message.role === "user" ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <Bot className="w-4 h-4 text-purple-400" />
                  )}
                </div>
                <div className={`px-4 py-2 rounded-lg ${
                  message.role === "user"
                    ? "bg-purple-500 text-white"
                    : "bg-zinc-800/50 text-zinc-100"
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  {isClient && (
                    <p className="text-xs mt-1 opacity-50">
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start mb-4"
            >
              <div className="flex gap-3 max-w-[80%]">
                <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-zinc-700">
                  <Bot className="w-4 h-4 text-purple-400" />
                </div>
                <div className="px-4 py-2 rounded-lg bg-zinc-800/50">
                  <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t border-zinc-800">
        <div className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your memories, patterns, or life insights..."
            className="flex-1 min-h-[60px] max-h-[120px] bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-500 resize-none"
            disabled={isLoading}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            className="text-xs border-zinc-700 hover:bg-zinc-800"
            onClick={() => setInput("What patterns do you see in my life?")}
          >
            Life Patterns
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs border-zinc-700 hover:bg-zinc-800"
            onClick={() => setInput("What have I learned this year?")}
          >
            Yearly Insights
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-xs border-zinc-700 hover:bg-zinc-800"
            onClick={() => setInput("Show me my growth areas")}
          >
            Personal Growth
          </Button>
        </div>
      </div>
    </div>
  );
} 