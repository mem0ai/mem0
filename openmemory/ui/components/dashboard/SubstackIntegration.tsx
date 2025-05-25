"use client";
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

export function SubstackIntegration() {
  const [substackUrl, setSubstackUrl] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "success" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState("");
  const [documentCount, setDocumentCount] = useState(0);
  
  const { user } = useAuth();

  // Fetch document count on mount
  useEffect(() => {
    fetchDocumentCount();
  }, []);

  const fetchDocumentCount = async () => {
    if (!user) return;
    try {
      const response = await apiClient.get("/api/v1/documents/count", {
        params: { document_type: "substack" }
      });
      setDocumentCount(response.data.count || 0);
    } catch (error) {
      console.error("Error fetching document count:", error);
    }
  };

  const handleSync = async () => {
    if (!substackUrl || !user) return;

    // Validate URL format
    const urlPattern = /^https?:\/\/([^.]+)\.substack\.com\/?$/;
    if (!urlPattern.test(substackUrl)) {
      setSyncStatus("error");
      setSyncMessage("Invalid URL format. Expected: https://username.substack.com");
      return;
    }

    setIsSyncing(true);
    setSyncStatus("idle");
    setSyncMessage("");

    try {
      // Call the sync endpoint
      const response = await apiClient.post("/api/v1/integrations/substack/sync", {
        substack_url: substackUrl,
        max_posts: 20
      });

      setSyncStatus("success");
      setSyncMessage(response.data.message || "Successfully synced Substack posts");
      
      // Refresh document count
      await fetchDocumentCount();
      
      // Clear URL after successful sync
      setSubstackUrl("");
    } catch (error: any) {
      setSyncStatus("error");
      setSyncMessage(error.response?.data?.detail || "Failed to sync Substack");
    } finally {
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
              placeholder="https://username.substack.com"
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

        {/* Document count */}
        {documentCount > 0 && (
          <div className="pt-2 border-t border-zinc-800">
            <p className="text-sm text-zinc-400">
              <span className="text-zinc-100 font-medium">{documentCount}</span> essays synced
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
} 