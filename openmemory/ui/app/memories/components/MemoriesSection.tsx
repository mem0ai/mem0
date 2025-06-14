import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Category, Client } from "../../../components/types";
import { MemoryTable } from "./MemoryTable";
import { MemoryPagination } from "./MemoryPagination";
import { CreateMemoryDialog } from "./CreateMemoryDialog";
import { PageSizeSelector } from "./PageSizeSelector";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useRouter, useSearchParams } from "next/navigation";
import { MemoryTableSkeleton } from "@/skeleton/MemoryTableSkeleton";

export function MemoriesSection() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { fetchMemories } = useMemoriesApi();
  const [memories, setMemories] = useState<any[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const currentPage = Number(searchParams.get("page")) || 1;
  const itemsPerPage = Number(searchParams.get("size")) || 10;
  const [selectedCategory, setSelectedCategory] = useState<Category | "all">(
    "all"
  );
  const [selectedClient, setSelectedClient] = useState<Client | "all">("all");

  useEffect(() => {
    const loadMemories = async () => {
      setIsLoading(true);
      try {
        const searchQuery = searchParams.get("search") || "";
        const result = await fetchMemories(
          searchQuery,
          currentPage,
          itemsPerPage
        );
        setMemories(result.memories);
        setTotalItems(result.total);
        setTotalPages(result.pages);
      } catch (error) {
        console.error("Failed to fetch memories:", error);
      }
      setIsLoading(false);
    };

    loadMemories();
  }, [currentPage, itemsPerPage, fetchMemories, searchParams]);

  const setCurrentPage = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", page.toString());
    params.set("size", itemsPerPage.toString());
    router.push(`?${params.toString()}`);
  };

  const handlePageSizeChange = (size: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", "1"); // Reset to page 1 when changing page size
    params.set("size", size.toString());
    router.push(`?${params.toString()}`);
  };

  if (isLoading) {
    return (
      <div className="w-full bg-transparent">
        <MemoryTableSkeleton />
        <div className="flex items-center justify-between mt-4">
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
          <div className="h-8 w-48 bg-muted rounded animate-pulse" />
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-transparent">
      <div>
        {memories.length > 0 ? (
          <>
            <MemoryTable />
            <div className="flex items-center justify-between mt-4">
              <PageSizeSelector
                pageSize={itemsPerPage}
                onPageSizeChange={handlePageSizeChange}
              />
              <div className="text-sm text-zinc-500 mr-2">
                Showing {(currentPage - 1) * itemsPerPage + 1} to{" "}
                {Math.min(currentPage * itemsPerPage, totalItems)} of{" "}
                {totalItems} memories
              </div>
              <MemoryPagination
                currentPage={currentPage}
                totalPages={totalPages}
                setCurrentPage={setCurrentPage}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full"></div>
              <div className="relative rounded-full bg-card border border-border p-6">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-primary"
                >
                  <path d="M12 2v20M2 12h20M8 8l8 8M16 8l-8 8" opacity="0.3"/>
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" opacity="0.2"/>
                </svg>
              </div>
            </div>
            <h3 className="text-xl font-semibold text-foreground mb-2">
              {selectedCategory !== "all" || selectedClient !== "all"
                ? "No memories match your filters"
                : "Start Building Your Memory Bank"}
            </h3>
            <p className="text-muted-foreground mb-6 max-w-md">
              {selectedCategory !== "all" || selectedClient !== "all"
                ? "Try adjusting your filters to see more memories"
                : "Your AI conversations will appear here. Connect an app above and start chatting to create your first memory!"}
            </p>
            {selectedCategory !== "all" || selectedClient !== "all" ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedCategory("all");
                  setSelectedClient("all");
                }}
              >
                Clear Filters
              </Button>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <CreateMemoryDialog />
                <p className="text-xs text-muted-foreground">
                  Or start chatting with Claude, Cursor, or any connected app
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
