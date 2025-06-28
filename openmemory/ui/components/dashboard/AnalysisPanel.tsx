"use client";

import { motion } from "framer-motion";
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import apiClient from "@/lib/apiClient"; // Import the api client
import ReactMarkdown from 'react-markdown';

export function AnalysisPanel() {
  const { accessToken } = useAuth();
  const { toast } = useToast();
  const [narrative, setNarrative] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    // Automatically fetch cached narrative on page load
    const fetchCachedNarrative = async () => {
      if (!accessToken) return;
      
      try {
        setIsLoading(true);
        const response = await apiClient.get('/api/v1/memories/narrative');
        
        if (response.data && response.data.narrative) {
          setNarrative(response.data.narrative);
          setError(''); // Clear any previous errors
        }
      } catch (err: any) {
        if (err.response?.status === 204) {
          // No narrative available yet - this is expected for new users
          setError('');
          setNarrative('');
        } else {
          console.error('Failed to fetch cached narrative:', err);
          setError('Failed to load narrative');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchCachedNarrative();
  }, [accessToken]);

  const handleGenerateNarrative = async () => {
    setIsGenerating(true);
    setError('');

    try {
      // Step 1: Fetch all memories from the backend
      const memoriesResponse = await apiClient.get('/api/v1/memories/?page=1&size=1000'); // Fetch up to 1000 memories
      const memories = memoriesResponse.data.items;

      if (!memories || memories.length === 0) {
        throw new Error("You don't have any memories yet to generate a narrative.");
      }

      // Step 2: Call the local UI route to generate the narrative
      const narrativeResponse = await fetch('/api/narrative/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ memories }),
      });

      if (!narrativeResponse.ok) {
        const errorData = await narrativeResponse.json();
        throw new Error(errorData.detail || 'Failed to generate narrative.');
      }

      const { narrative } = await narrativeResponse.json();

      if (narrative) {
        setNarrative(narrative);
        toast({
          title: 'Narrative Generated',
          description: 'Your life narrative has been generated.',
        });
      } else {
        throw new Error('Invalid response from server.');
      }
    } catch (err: any) {
      const errorMessage = err.message || 'An unknown error occurred.';
      setError(errorMessage);
      toast({
        variant: 'destructive',
        title: 'Error Generating Narrative',
        description: errorMessage,
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-card/20 backdrop-blur-sm border border-border rounded-xl p-6 h-full flex flex-col"
    >
      <div className="mb-4">
        <h2 className="text-xl font-bold text-foreground">Your Life's Narrative</h2>
         <p className="text-sm text-muted-foreground">
          A summary of your life based on your memories.
        </p>
      </div>
      <div className="flex-grow flex flex-col items-center justify-center min-h-[150px]">
        {isLoading ? (
          <div className="text-center">
            <div className="animate-pulse text-primary mb-2 font-medium">
              Loading your narrative...
            </div>
          </div>
        ) : isGenerating ? (
          <div className="text-center">
            <div className="animate-pulse text-primary mb-2 font-medium">
              Generating Narrative...
            </div>
          </div>
        ) : error ? (
            <div className='text-center'>
                <p className="text-destructive mb-4">{error}</p>
                <Button onClick={handleGenerateNarrative} disabled={isGenerating}>
                    {isGenerating ? 'Generating...' : 'Try Again'}
                </Button>
            </div>
        ) : narrative ? (
          <div className="text-muted-foreground text-sm prose dark:prose-invert prose-sm max-w-none h-full overflow-y-auto pr-2">
            <ReactMarkdown>{narrative}</ReactMarkdown>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-muted-foreground mb-4">
              Your narrative will appear here once you have enough memories (5+). 
              You can also generate one manually if you'd like.
            </p>
            <Button onClick={handleGenerateNarrative} disabled={isGenerating}>
              {isGenerating ? 'Generating...' : 'Generate Narrative'}
            </Button>
          </div>
        )}
      </div>
      {/* Regenerate Button - always visible if a narrative exists */}
      {!isLoading && !isGenerating && !error && narrative && (
        <div className="mt-4 pt-4 border-t border-border/50 flex justify-end">
            <Button onClick={handleGenerateNarrative} disabled={isGenerating} variant="ghost" size="sm">
              {isGenerating ? 'Regenerating...' : 'Regenerate Narrative'}
            </Button>
        </div>
      )}
    </motion.div>
  );
} 