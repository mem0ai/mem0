"use client";

import { useEffect, useState } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { ComparisonView } from "@/app/memories/components/ComparisonView";
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
  const [activeTab, setActiveTab] = useState("regular");

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
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full max-w-md grid-cols-2 mb-4">
                <TabsTrigger value="regular" className="flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Regular View
                  <Badge variant="outline" className="ml-1 bg-yellow-500/20 text-yellow-300 border-yellow-500/30 text-xs">
                    Fast
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="comparison" className="flex items-center gap-2">
                  <Network className="h-4 w-4" />
                  Comparison
                  <Badge variant="outline" className="ml-1 bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-xs">
                    NEW
                  </Badge>
                </TabsTrigger>
              </TabsList>
              <TabsContent value="regular">
                <MemoriesSection />
              </TabsContent>
              <TabsContent value="comparison">
                <ComparisonView />
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
    </div>
  );
}
