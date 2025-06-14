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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchNarrative = async () => {
      if (!accessToken) {
        setIsLoading(false);
        return;
      }
      
      setIsLoading(true);
      try {
        const response = await apiClient.get('/api/v1/user/narrative');
        
        if (response.data && response.data.narrative) {
          setNarrative(response.data.narrative);
        }
      } catch (err: any) {
        if (err.response && err.response.status === 404) {
          console.log("No existing narrative found.");
        } else {
          console.error("Failed to fetch existing narrative:", err);
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchNarrative();
  }, [accessToken]);

  const handleGenerateNarrative = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/api/v1/user/narrative');

      if (response.data && response.data.narrative) {
        setNarrative(response.data.narrative);
        toast({
          title: narrative ? 'Narrative Regenerated' : 'Narrative Generated',
          description: 'Your life narrative has been updated.',
        });
      } else {
        throw new Error('Invalid response from server.');
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || err.message || 'Failed to generate narrative.';
      setError(errorMessage);
      toast({
        variant: 'destructive',
        title: 'Error Generating Narrative',
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-zinc-900/20 backdrop-blur-sm border border-zinc-800 rounded-xl p-6 h-full flex flex-col"
    >
      <div className="mb-4">
        <h2 className="text-xl font-bold text-white">Your Life's Narrative</h2>
         <p className="text-sm text-zinc-400">
          A summary of your life based on your memories.
        </p>
      </div>
      <div className="flex-grow flex flex-col items-center justify-center min-h-[150px]">
        {isLoading ? (
          <div className="text-center">
            <div className="animate-pulse text-blue-400 mb-2 font-medium">
              Loading Narrative...
            </div>
          </div>
        ) : error ? (
            <div className='text-center'>
                <p className="text-red-400 mb-4">{error}</p>
                <Button onClick={handleGenerateNarrative} disabled={isLoading}>
                    {isLoading ? 'Generating...' : 'Try Again'}
                </Button>
            </div>
        ) : narrative ? (
          <div className="text-zinc-300 text-sm prose prose-invert prose-sm max-w-none h-full overflow-y-auto pr-2">
            <ReactMarkdown>{narrative}</ReactMarkdown>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-zinc-400 mb-4">
              Click the button to generate a narrative from your memories.
            </p>
            <Button onClick={handleGenerateNarrative} disabled={isLoading}>
              {isLoading ? 'Generating...' : 'Generate Narrative'}
            </Button>
          </div>
        )}
      </div>
      {/* Regenerate Button - always visible if a narrative exists */}
      {!isLoading && !error && narrative && (
        <div className="mt-4 pt-4 border-t border-zinc-800/50 flex justify-end">
            <Button onClick={handleGenerateNarrative} disabled={isLoading} variant="ghost" size="sm">
              {isLoading ? 'Regenerating...' : 'Regenerate Narrative'}
            </Button>
        </div>
      )}
    </motion.div>
  );
} 