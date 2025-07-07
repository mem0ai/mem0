"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/apiClient";
import { sessionUtils } from "@/lib/sessionUtils";
import { RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";

interface RefreshAllButtonProps {
  onRefreshComplete?: () => void;
  showStatus?: boolean; // New prop to control whether to show status text
}

export function RefreshAllButton({ onRefreshComplete, showStatus = true }: RefreshAllButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<string | null>(null);
  const [hasSessionRefreshed, setHasSessionRefreshed] = useState(false);
  const { user } = useAuth();
  const { toast } = useToast();

  // Check session state on mount
  useEffect(() => {
    setHasSessionRefreshed(sessionUtils.hasSessionRefreshed());
    setLastRefreshTime(sessionUtils.getLastRefreshTime());
  }, []);

  // Auto-refresh on first load if not done this session
  useEffect(() => {
    if (user && !hasSessionRefreshed && !isRefreshing) {
      console.log("🔄 Triggering session auto-refresh");
      handleRefreshAll(true); // true indicates this is an auto-refresh
    }
  }, [user, hasSessionRefreshed, isRefreshing]);

  const handleRefreshAll = async (isAutoRefresh = false) => {
    if (!user || isRefreshing) return;

    setIsRefreshing(true);
    
    if (!isAutoRefresh) {
      toast({
        title: "Refreshing Integrations",
        description: "Starting refresh for all your integrations...",
      });
    }

    try {
      const response = await apiClient.post("/api/v1/integrations/refresh-all");
      const data = response.data;

      // Mark session as refreshed using utility
      sessionUtils.markSessionRefreshed();
      setHasSessionRefreshed(true);
      setLastRefreshTime(sessionUtils.getLastRefreshTime());

      // Show success toast
      const successMessage = isAutoRefresh 
        ? `Auto-refresh completed: ${data.message}`
        : `Manual refresh completed: ${data.message}`;

      toast({
        title: "Refresh Complete",
        description: successMessage,
        action: data.successful_refreshes > 0 ? (
          <div className="flex items-center gap-1 text-green-600">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-sm">{data.successful_refreshes} refreshing</span>
          </div>
        ) : undefined,
      });

      // Show warnings if any
      if (data.failed_refreshes > 0) {
        toast({
          variant: "destructive",
          title: "Some Refreshes Failed",
          description: `${data.failed_refreshes} integrations failed to refresh`,
        });
      }

      // Notify parent component
      onRefreshComplete?.();

      console.log("Refresh results:", data);

    } catch (error: any) {
      console.error("Refresh failed:", error);
      
      toast({
        variant: "destructive",
        title: "Refresh Failed",
        description: error.response?.data?.detail || "Failed to refresh integrations",
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  if (!user) return null;

  if (showStatus) {
    // Full component with status (original behavior)
    return (
      <div className="flex items-center gap-3">
        <Button
          onClick={() => handleRefreshAll(false)}
          disabled={isRefreshing}
          variant="outline"
          size="sm"
          className="flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh All'}
        </Button>
        
        {lastRefreshTime && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              {hasSessionRefreshed ? (
                <CheckCircle2 className="w-3 h-3 text-green-500" />
              ) : (
                <AlertTriangle className="w-3 h-3 text-yellow-500" />
              )}
              <span>Last refresh: {sessionUtils.formatRefreshTime(lastRefreshTime)}</span>
            </div>
          </div>
        )}
      </div>
    );
  } else {
    // Just the button without status
    return (
      <Button
        onClick={() => handleRefreshAll(false)}
        disabled={isRefreshing}
        variant="outline"
        size="sm"
        className="flex items-center gap-2"
      >
        <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        {isRefreshing ? 'Refreshing...' : 'Refresh All'}
      </Button>
    );
  }
}

// Separate component for just the refresh status
export function RefreshStatus() {
  const [lastRefreshTime, setLastRefreshTime] = useState<string | null>(null);
  const [hasSessionRefreshed, setHasSessionRefreshed] = useState(false);

  useEffect(() => {
    setHasSessionRefreshed(sessionUtils.hasSessionRefreshed());
    setLastRefreshTime(sessionUtils.getLastRefreshTime());
  }, []);

  if (!lastRefreshTime) return null;

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <div className="flex items-center gap-1">
        {hasSessionRefreshed ? (
          <CheckCircle2 className="w-3 h-3 text-green-500" />
        ) : (
          <AlertTriangle className="w-3 h-3 text-yellow-500" />
        )}
        <span>Last refresh: {sessionUtils.formatRefreshTime(lastRefreshTime)}</span>
      </div>
    </div>
  );
} 