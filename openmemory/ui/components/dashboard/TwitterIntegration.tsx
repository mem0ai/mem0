"use client";
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

export function TwitterIntegration() {
  const [twitterUsername, setTwitterUsername] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "success" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState("");
  const [tweetCount, setTweetCount] = useState(0);
  
  const { user } = useAuth();

  // Fetch tweet count on mount
  useEffect(() => {
    fetchTweetCount();
  }, []);

  const fetchTweetCount = async () => {
    if (!user) return;
    try {
      // For now, we'll count memories with twitter metadata
      const response = await apiClient.get("/api/v1/memories", {
        params: { 
          page: 1,
          size: 1,
          search_query: "tweeted"
        }
      });
      // This is a rough estimate - in production you might want a dedicated endpoint
      setTweetCount(response.data.total || 0);
    } catch (error) {
      console.error("Error fetching tweet count:", error);
    }
  };

  const handleSync = async () => {
    if (!twitterUsername || !user) return;

    setIsSyncing(true);
    setSyncStatus("idle");
    setSyncMessage("");

    try {
      // Call the sync endpoint
      const response = await apiClient.post("/api/v1/integrations/sync/twitter", null, {
        params: {
          username: twitterUsername.replace('@', ''), // Remove @ if present
          max_posts: 40
        }
      });

      setSyncStatus("success");
      setSyncMessage(response.data.message || "Successfully synced tweets");
      
      // Refresh tweet count
      await fetchTweetCount();
      
      // Clear username after successful sync
      setTwitterUsername("");
    } catch (error: any) {
      setSyncStatus("error");
      setSyncMessage(error.response?.data?.detail || "Failed to sync Twitter posts. The user might be private or the service is temporarily unavailable.");
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <Card className="bg-zinc-900/50 border-zinc-800 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-medium text-zinc-100">
          Twitter/X Integration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-zinc-400 mb-3">
            Sync recent tweets to capture your thoughts and conversations
          </p>
          {isSyncing && (
            <p className="text-xs text-zinc-500 mb-2">
              Fetching your latest tweets...
            </p>
          )}
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="@username or username"
              value={twitterUsername}
              onChange={(e) => setTwitterUsername(e.target.value)}
              className="bg-zinc-950/50 border-zinc-800 text-zinc-300"
              disabled={isSyncing}
            />
            <Button
              onClick={handleSync}
              disabled={isSyncing || !twitterUsername}
              className="bg-[#1DA1F2] hover:bg-[#1DA1F2]/80 text-white"
            >
              {isSyncing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                "Sync Tweets"
              )}
            </Button>
          </div>
        </div>

        {/* Status message */}
        {syncMessage && (
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

        {/* Tweet count */}
        {tweetCount > 0 && (
          <div className="pt-2 border-t border-zinc-800">
            <p className="text-sm text-zinc-400">
              <span className="text-zinc-100 font-medium">{tweetCount}</span> tweets synced
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
} 