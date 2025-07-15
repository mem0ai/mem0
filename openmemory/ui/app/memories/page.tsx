"use client";

import { useEffect, useState } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { useRouter, useSearchParams } from "next/navigation";
import "@/styles/animation.css";
import UpdateMemory from "@/components/shared/update-memory";
import { useUI } from "@/hooks/useUI";
import { DeepQueryDialog } from "./components/DeepQueryDialog";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { ProtectedRoute } from "@/components/ProtectedRoute";

export default function MemoriesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { updateMemoryDialog, handleCloseUpdateMemoryDialog } = useUI();
  const { fetchMemories } = useMemoriesApi();
  const [memories, setMemories] = useState<any[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const filters = useSelector((state: RootState) => state.filters.apps);

  const currentPage = Number(searchParams.get("page")) || 1;
  const itemsPerPage = Number(searchParams.get("size")) || 10;

  useEffect(() => {
    loadMemories();
  }, [currentPage, itemsPerPage, searchParams, filters]);

  const loadMemories = async () => {
    setIsLoading(true);
    try {
      const searchQuery = searchParams.get("search") || "";
      const result = await fetchMemories(
        searchQuery,
        currentPage,
        itemsPerPage,
        {
          apps: filters.selectedApps,
          categories: filters.selectedCategories,
          sortColumn: filters.sortColumn,
          sortDirection: filters.sortDirection,
          showArchived: filters.showArchived,
        }
      );
      setMemories(result.memories);
      setTotalItems(result.total);
      setTotalPages(result.pages);
    } catch (error) {
      console.error("Failed to fetch memories:", error);
    }
    setIsLoading(false);
  };

  const setCurrentPage = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", page.toString());
    router.push(`?${params.toString()}`);
  };

  const handlePageSizeChange = (size: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", "1");
    params.set("size", size.toString());
    router.push(`?${params.toString()}`);
  };

  const handleClearFilters = () => {
    // This will be handled by the FilterComponent's Redux action
  };

  return (
    <ProtectedRoute>
      <div className="">
      <UpdateMemory
        memoryId={updateMemoryDialog.memoryId || ""}
        memoryContent={updateMemoryDialog.memoryContent || ""}
        open={updateMemoryDialog.isOpen}
        onOpenChange={handleCloseUpdateMemoryDialog}
      />
      <main className="flex-1 py-6">
        <div className="container">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4 mt-1 pb-4 animate-fade-slide-down">
            <MemoryFilters onFilterChange={loadMemories} />
            <DeepQueryDialog />
          </div>
          <div className="animate-fade-slide-down delay-1">
            <MemoriesSection
              memories={memories}
              totalItems={totalItems}
              totalPages={totalPages}
              currentPage={currentPage}
              itemsPerPage={itemsPerPage}
              isLoading={isLoading}
              setCurrentPage={setCurrentPage}
              onPageSizeChange={handlePageSizeChange}
              onClearFilters={handleClearFilters}
              hasActiveFilters={
                filters.selectedApps.length > 0 ||
                filters.selectedCategories.length > 0 ||
                filters.showArchived
              }
            />
          </div>
        </div>
      </main>
    </div>
    </ProtectedRoute>
  );
}
