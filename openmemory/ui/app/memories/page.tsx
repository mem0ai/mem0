"use client";

import { useEffect, useState } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { EnrichedMemoriesView } from "@/app/memories/components/EnrichedMemoriesView";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { useRouter, useSearchParams } from "next/navigation";
import "@/styles/animation.css";
import UpdateMemory from "@/components/shared/update-memory";
import { useUI } from "@/hooks/useUI";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Zap, Network } from "lucide-react";

export default function MemoriesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { updateMemoryDialog, handleCloseUpdateMemoryDialog } = useUI();

  // Read tab from URL params, default to "regular"
  const tabParam = searchParams.get("tab") || "regular";
  const [activeTab, setActiveTab] = useState(tabParam);

  // Sync activeTab with URL params
  useEffect(() => {
    setActiveTab(tabParam);
  }, [tabParam]);

  // Update URL when tab changes
  const handleTabChange = (value: string) => {
    setActiveTab(value);
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", value);
    router.push(`?${params.toString()}`);
  };

  useEffect(() => {
    // Set default pagination values if not present in URL
    if (!searchParams.has("page") || !searchParams.has("size")) {
      const params = new URLSearchParams(searchParams.toString());
      if (!searchParams.has("page")) params.set("page", "1");
      if (!searchParams.has("size")) params.set("size", "10");
      router.push(`?${params.toString()}`);
    }
  }, []);

  return (
    <div className="">
      <UpdateMemory
        memoryId={updateMemoryDialog.memoryId || ""}
        memoryContent={updateMemoryDialog.memoryContent || ""}
        open={updateMemoryDialog.isOpen}
        onOpenChange={handleCloseUpdateMemoryDialog}
      />
      <main className="flex-1 py-6">
        <div className="container">
          <div className="mt-1 pb-4 animate-fade-slide-down">
            <MemoryFilters />
          </div>
          <div className="animate-fade-slide-down delay-1">
            <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
              <TabsList className="grid w-full max-w-md grid-cols-2 mb-4">
                <TabsTrigger value="regular" className="flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Regular View
                  <Badge variant="outline" className="ml-1 bg-yellow-500/20 text-yellow-300 border-yellow-500/30 text-xs">
                    Fast
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="enriched" className="flex items-center gap-2">
                  <Network className="h-4 w-4" />
                  Enriched
                  <Badge variant="outline" className="ml-1 bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-xs">
                    Graph
                  </Badge>
                </TabsTrigger>
              </TabsList>
              <TabsContent value="regular">
                <MemoriesSection />
              </TabsContent>
              <TabsContent value="enriched">
                <EnrichedMemoriesView />
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
    </div>
  );
}
