"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, User, Bot, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useAuth } from "@/contexts/AuthContext";
import ReactMarkdown from 'react-markdown';
import apiClient from "@/lib/apiClient";
import { createClient } from '@supabase/supabase-js';

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
  const [selectedMemoryDetails, setSelectedMemoryDetails] = useState<any>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { memories, fetchMemories } = useMemoriesApi();
  const { user } = useAuth();

  // Initialize client-side only
  useEffect(() => {
    setIsClient(true);
    setMessages([
      {
        id: "1",
        role: "assistant",
        content: "Hello! I'm your personal AI assistant. I can help you explore your life's journey by analyzing your memories and providing insights about patterns, experiences, and growth. Ask me anything about your memories or life insights!",
        timestamp: new Date()
      }
    ]);
    
    // Fetch memories when component mounts
    fetchMemories().then(() => {
      console.log('Memories loaded:', memories);
    }).catch(err => {
      console.error('Error loading memories:', err);
    });
  }, []);

  // Debug log memories
  useEffect(() => {
    console.log('Current memories:', memories);
    console.log('Number of memories:', memories.length);
  }, [memories]);

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
      // Fetch the memory details when a memory is selected
      fetchMemoryDetails(selectedMemory);
    }
  }, [selectedMemory]);

  const fetchMemoryDetails = async (memoryId: string) => {
    try {
      const response = await apiClient.get(`/api/v1/memories/${memoryId}`);
      setSelectedMemoryDetails(response.data);
      
      // Update the input with memory details
      const memoryContent = response.data.content || response.data.text || 'Unknown memory content';
      const memoryDate = response.data.created_at ? new Date(response.data.created_at).toLocaleDateString() : 'Unknown date';
      const appName = response.data.app_name || 'Unknown source';
      
      setInput(`Tell me more about this memory from ${appName} on ${memoryDate}: "${memoryContent}"`);
      textareaRef.current?.focus();
    } catch (error) {
      console.error('Error fetching memory details:', error);
      setInput(`Tell me more about this memory: ${memoryId}`);
      textareaRef.current?.focus();
    }
  };

  const callGeminiAPI = async (userMessage: string, memoriesContext: any[], selectedMemory: any) => {
    try {
      // Check if we're in local development mode
      const localUserId = process.env.NEXT_PUBLIC_USER_ID;
      let accessToken;
      
      if (localUserId) {
        console.log('ChatInterface: Local development mode detected, using local token');
        accessToken = 'local-dev-token';
      } else {
        // Production mode - get token from Supabase
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
        const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
        const supabase = createClient(supabaseUrl, supabaseAnonKey);
        
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError || !session?.access_token) {
          throw new Error('Unable to get authentication token');
        }
        
        accessToken = session.access_token;
      }

      // Prepare context from memories
      const memoryContext = memoriesContext.slice(0, 20).map(m => 
        `Memory: ${m.memory} (from ${m.app_name || 'unknown app'} on ${new Date(m.created_at).toLocaleDateString()})`
      ).join('\n');

      // Add selected memory details if available
      let selectedMemoryContext = '';
      if (selectedMemory) {
        selectedMemoryContext = `\n\nSELECTED MEMORY DETAILS:\n`;
        selectedMemoryContext += `ID: ${selectedMemory.id}\n`;
        selectedMemoryContext += `Content: ${selectedMemory.content}\n`;
        selectedMemoryContext += `Created: ${selectedMemory.created_at}\n`;
        selectedMemoryContext += `App: ${selectedMemory.app_name || 'Unknown'}\n`;
        selectedMemoryContext += `Categories: ${selectedMemory.categories?.join(', ') || 'None'}\n`;
        if (selectedMemory.metadata_) {
          selectedMemoryContext += `Metadata: ${JSON.stringify(selectedMemory.metadata_, null, 2)}\n`;
        }
      }

      const prompt = `You are a personal AI assistant with access to the user's memories. Be concise and direct in your responses.

MEMORIES CONTEXT:
${memoryContext}${selectedMemoryContext}

USER QUESTION: ${userMessage}

Provide a focused, concise response (2-3 paragraphs max). If discussing a specific memory, highlight key insights and connections without being verbose.`;

      const response = await fetch('/api/chat/gemini', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          prompt,
          memories: memoriesContext,
          selectedMemory: selectedMemory
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
      const aiResponse = await callGeminiAPI(currentInput, memories, selectedMemoryDetails);
      
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
      // Clear selected memory details after sending
      setSelectedMemoryDetails(null);
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
                  {message.role === "assistant" ? (
                    <div className="text-sm prose prose-invert prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                      <ReactMarkdown>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  )}
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