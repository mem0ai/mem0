"use client";
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { constants } from "@/components/shared/source-app";
import Image from "next/image";
import { useAppsApi } from "@/hooks/useAppsApi";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";

export function SubstackCard() {
  const [substackUrl, setSubstackUrl] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "success" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState("");
  const [documentCount, setDocumentCount] = useState(0);
  
  const { fetchApps } = useAppsApi();
  const { user } = useAuth();
  const appConfig = constants.substack;

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
      
      // Refresh apps and document count
      await fetchApps();
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
    <Card className="bg-zinc-900 text-white border-zinc-800">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-1">
          <div className="relative z-10 rounded-full overflow-hidden bg-[#FF6719] w-6 h-6 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <h2 className="text-xl font-semibold">{appConfig.name}</h2>
        </div>
      </CardHeader>
      <CardContent className="pb-4 my-1">
        <div className="space-y-4">
          <div>
            <p className="text-zinc-400 text-sm mb-2">Sync your Substack essays</p>
            <div className="flex gap-2">
              <Input
                type="url"
                placeholder="https://username.substack.com"
                value={substackUrl}
                onChange={(e) => setSubstackUrl(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-white"
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
                  "Sync"
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
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-zinc-400 text-sm mb-1">Essays Stored</p>
              <p className="text-xl font-medium">{documentCount} Documents</p>
            </div>
            <div>
              <p className="text-zinc-400 text-sm mb-1">Status</p>
              <p className="text-xl font-medium">
                <span className="text-green-400">Active</span>
              </p>
            </div>
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t border-zinc-800 p-0 px-6 py-2 flex justify-between items-center">
        <div className="bg-green-800 text-white rounded-lg px-2 py-0.5 flex items-center text-sm">
          <span className="h-2 w-2 my-auto mr-1 rounded-full inline-block bg-current"></span>
          Ready to Sync
        </div>
        <div className="text-sm text-zinc-400">
          Powered by RSS
        </div>
      </CardFooter>
    </Card>
  );
} 