"use client";
import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Loader2, CheckCircle, AlertCircle, FileText } from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

export function SubstackIntegration() {
  const [substackUrl, setSubstackUrl] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "success" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState("");
  const [documentCount, setDocumentCount] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  
  const { user } = useAuth();
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch document count on mount
  useEffect(() => {
    fetchDocumentCount();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const fetchDocumentCount = async () => {
    if (!user) return;
    try {
      const response = await apiClient.get("/api/v1/integrations/documents/count", {
        params: { document_type: "substack" }
      });
      setDocumentCount(response.data.count || 0);
    } catch (error) {
      console.error("Error fetching document count:", error);
    }
  };

  const normalizeSubstackUrl = (url: string): string => {
    url = url.trim();
    
    // If no protocol, add https://
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = `https://${url}`;
    }
    
    // Remove trailing slash
    url = url.replace(/\/$/, '');
    
    return url;
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const response = await apiClient.get(`/api/v1/integrations/tasks/${taskId}`);
      const task = response.data;
      
      setProgress(task.progress || 0);
      setProgressMessage(task.progress_message || "Processing...");
      
      if (task.status === "completed") {
        // Task completed successfully
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        
        setIsSyncing(false);
        setSyncStatus("success");
        setSyncMessage(task.result?.message || "Successfully synced Substack posts");
        setTaskId(null);
        setProgress(100);
        
        // Refresh document count
        await fetchDocumentCount();
        
        // Clear URL after successful sync
        setSubstackUrl("");
      } else if (task.status === "failed") {
        // Task failed
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        
        setIsSyncing(false);
        setSyncStatus("error");
        setSyncMessage(task.error || "Failed to sync Substack");
        setTaskId(null);
        setProgress(0);
      }
      // If status is "pending" or "running", continue polling
    } catch (error) {
      console.error("Error polling task status:", error);
      // Continue polling even if there's an error
    }
  };

  const handleSync = async () => {
    if (!substackUrl || !user) return;

    // Normalize the URL first
    const normalizedUrl = normalizeSubstackUrl(substackUrl);

    // Validate normalized URL format
    const urlPattern = /^https?:\/\/([^.]+)\.substack\.com\/?$/;
    if (!urlPattern.test(normalizedUrl)) {
      setSyncStatus("error");
      setSyncMessage("Invalid URL format. Expected: https://username.substack.com or username.substack.com");
      return;
    }

    setIsSyncing(true);
    setSyncStatus("idle");
    setSyncMessage("");
    setProgress(0);
    setProgressMessage("Starting sync...");

    try {
      // Call the sync endpoint with the normalized URL
      const response = await apiClient.post("/api/v1/integrations/substack/sync", {
        substack_url: normalizedUrl, // Use normalized URL
        max_posts: 20
      });

      // Handle background task response
      if (response.data.task_id) {
        setTaskId(response.data.task_id);
        setSyncMessage("Sync started in background...");
        
        // Start polling for progress
        pollIntervalRef.current = setInterval(() => {
          pollTaskStatus(response.data.task_id);
        }, 2000); // Poll every 2 seconds
      } else {
        // Old sync response (synchronous)
        setSyncStatus("success");
        setSyncMessage(response.data.message || "Successfully synced Substack posts");
        setIsSyncing(false);
        await fetchDocumentCount();
        setSubstackUrl("");
      }
    } catch (error: any) {
      setSyncStatus("error");
      setSyncMessage(error.response?.data?.detail || "Failed to sync Substack");
      setIsSyncing(false);
    }
  };

  return (
    <Card className="bg-zinc-900/50 border-zinc-800 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-medium text-zinc-100">
          Substack Integration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-zinc-400 mb-3">
            Sync your Substack essays to build a comprehensive memory bank
          </p>
          <div className="flex gap-2">
            <Input
              type="url"
              placeholder="username.substack.com or https://username.substack.com"
              value={substackUrl}
              onChange={(e) => setSubstackUrl(e.target.value)}
              className="bg-zinc-950/50 border-zinc-800 text-zinc-300"
              disabled={isSyncing}
            />
            <Button
              onClick={handleSync}
              disabled={isSyncing || !substackUrl}
              className="bg-[#FF6719] hover:bg-[#FF6719]/80 text-white"
            >
              {isSyncing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                "Sync Essays"
              )}
            </Button>
          </div>
        </div>

        {/* Progress bar and status when syncing */}
        {isSyncing && (
          <div className="space-y-3">
            <Progress value={progress} className="h-2" />
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <FileText className="h-4 w-4" />
              <span>{progressMessage}</span>
            </div>
            {progress > 0 && (
              <p className="text-xs text-zinc-500">
                Essays are being added to your memory as they sync. Advanced processing happens in the background.
              </p>
            )}
          </div>
        )}

        {/* Status message */}
        {syncMessage && !isSyncing && (
          <div className={`flex items-center gap-2 text-sm ${
            syncStatus === "success" ? "text-green-400" : "text-red-400"
          }`}>
            {syncStatus === "success" ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            {syncMessage}
          </div>
        )}

        {/* Document count */}
        {documentCount > 0 && (
          <div className="pt-2 border-t border-zinc-800">
            <div className="flex items-center gap-2 text-sm text-zinc-400">
              <FileText className="h-4 w-4" />
              <span>
                <span className="text-zinc-100 font-medium">{documentCount}</span> essays synced and searchable
              </span>
            </div>
            <p className="text-xs text-zinc-500 mt-1">
              Your essays are being processed in the background for enhanced search capabilities.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
} 