"use client";

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Sparkles } from "lucide-react";
import { useMemoriesApi } from '@/hooks/useMemoriesApi';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { createClient } from '@supabase/supabase-js';

export function DeepQueryDialog() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState('');
  const { memories, fetchMemories } = useMemoriesApi();
  const { user } = useAuth();

  useEffect(() => {
    if (open) {
      fetchMemories();
    }
  }, [open, fetchMemories]);

  const handleQuery = async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setResult('');

    try {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
      const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;
      const supabase = createClient(supabaseUrl, supabaseAnonKey);
      
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      
      if (sessionError || !session?.access_token) {
        throw new Error('Unable to get authentication token');
      }
      
      const accessToken = session.access_token;
      
      const memoryContext = memories.map(m => 
        `Memory from ${m.app_name || 'unknown app'} on ${new Date(m.created_at).toLocaleDateString()}: "${m.memory}"`
      ).join('\n');

      const prompt = `You are a deep reflection AI assistant. Your task is to analyze the user's memories in-depth to answer a profound question about their life. Go beyond surface-level answers and identify underlying themes, patterns, personal growth, and contradictions.

Here are all the user's memories:
${memoryContext}

The user's question is: "${query}"

Provide a thoughtful, multi-paragraph response that synthesizes information from across the memories to provide a comprehensive insight. Be insightful and empathetic in your analysis.`;

      const response = await fetch('/api/chat/gemini', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          prompt,
          memories: memories,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to get response from Gemini');
      }

      const data = await response.json();
      setResult(data.response);
      toast.success("Query completed!");

    } catch (error: any) {
      console.error("Deep query failed:", error);
      toast.error(error.message || "Failed to perform deep query.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => {
      setOpen(isOpen);
      if (!isOpen) {
        setQuery('');
        setResult('');
      }
    }}>
      <DialogTrigger asChild>
        <Button>
          <Sparkles className="mr-2 h-4 w-4" />
          Deep Life Query
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[525px]">
        <DialogHeader>
          <DialogTitle>Ask a Deep Life Query</DialogTitle>
          <DialogDescription>
            Ask a complex question about your life. The AI will analyze all your memories to find patterns and insights.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <Textarea
            placeholder="e.g., What are the most significant themes in my life over the past year?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-h-[100px]"
          />
          {isLoading && (
            <div className="flex items-center justify-center p-4">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          )}
          {result && !isLoading && (
            <div className="p-4 bg-muted/50 rounded-lg text-sm prose dark:prose-invert max-w-none">
              <p>{result}</p>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleQuery} disabled={isLoading || !query.trim()}>
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Ask"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 