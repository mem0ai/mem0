import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from "@/components/ui/use-toast";

interface UseAppSyncProps {
  app: { id: string; name: string; };
  onSyncStart?: (appId: string, taskId: string) => void;
}

export const useAppSync = ({ app, onSyncStart }: UseAppSyncProps) => {
  const { accessToken } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const handleSync = async (inputValue: string) => {
    if (!inputValue) {
      toast({
        variant: "destructive",
        title: "Input required",
        description: `Please enter your ${app.name} username or URL.`,
      });
      return;
    }

    setIsLoading(true);

    let endpoint: string;
    let requestBody: Record<string, string>;

    if (app.id === 'twitter') {
      endpoint = 'sync/twitter';
      requestBody = { username: inputValue };
    } else if (app.id === 'substack') {
      endpoint = 'substack/sync';
      requestBody = { substack_url: inputValue };
    } else {
      toast({
        variant: "destructive",
        title: "Unsupported app",
        description: `Sync not supported for ${app.name}.`,
      });
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`/api/v1/integrations/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify(requestBody)
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Sync failed');
      }

      if (result.task_id && onSyncStart) {
        onSyncStart(app.id, result.task_id);
      }

      toast({
        title: "Sync Started",
        description: `${app.name} sync is in progress. Memories will be available shortly.`,
      });

      return true; // Indicate success
    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Sync Error",
        description: error.message || `Failed to start ${app.name} sync.`,
      });
      return false; // Indicate failure
    } finally {
      setIsLoading(false);
    }
  };

  return { isLoading, handleSync };
}; 