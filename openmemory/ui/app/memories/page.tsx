"use client";

import { useEffect } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { useRouter, useSearchParams } from "next/navigation";
import "@/styles/animation.css";
import UpdateMemory from "@/components/shared/update-memory";
import { useUI } from "@/hooks/useUI";

export default function MemoriesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { updateMemoryDialog, handleCloseUpdateMemoryDialog } = useUI();
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
            <MemoriesSection />
          </div>
        </div>
      </main>
    </div>
  );
}
