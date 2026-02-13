"use client";

import { useState, useEffect } from "react";
import { useMemoriesApi, EnrichedMemory } from "@/hooks/useMemoriesApi";
import { useSearchParams, useRouter } from "next/navigation";
import { EnrichedMemoryCard } from "@/components/EnrichedMemoryCard";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Network } from "lucide-react";
import { MemoryPagination } from "./MemoryPagination";

export function EnrichedMemoriesView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { fetchEnrichedMemories } = useMemoriesApi();
  const [enrichedMemories, setEnrichedMemories] = useState<EnrichedMemory[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentPage = Number(searchParams.get("page")) || 1;
  const itemsPerPage = Number(searchParams.get("size")) || 10;

  useEffect(() => {
    const loadMemories = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const searchQuery = searchParams.get("search") || "";
        const result = await fetchEnrichedMemories(searchQuery, currentPage, itemsPerPage);
        setEnrichedMemories(result.memories);
        setTotal(result.total);
        setTotalPages(result.totalPages);
      } catch (error: any) {
        console.error("Failed to fetch enriched memories:", error);
        setError(error.message || "Failed to load enriched memories");
      }
      setIsLoading(false);
    };

    loadMemories();
  }, [currentPage, itemsPerPage, searchParams, fetchEnrichedMemories]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  // Count enrichment stats
  const enrichedCount = enrichedMemories.filter(m => m.graph_enriched).length;
  const totalEntities = enrichedMemories.reduce((sum, m) => sum + (m.entities?.length || 0), 0);
  const totalRelationships = enrichedMemories.reduce((sum, m) => sum + (m.relationships?.length || 0), 0);

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <Alert className="bg-emerald-950/30 border-emerald-900/50">
        <Network className="h-4 w-4 text-emerald-400" />
        <AlertTitle>Graph-Enriched Memories</AlertTitle>
        <AlertDescription className="mt-2">
          <p className="text-sm">
            Memories enriched with Neo4j graph data - entities have types (Person, Place, Date) and explicit relationships.
          </p>
          <div className="flex gap-4 mt-2 text-xs text-zinc-400">
            <span>📊 {enrichedCount}/{enrichedMemories.length} enriched</span>
            <span>🏷️ {totalEntities} entities</span>
            <span>🔗 {totalRelationships} relationships</span>
          </div>
        </AlertDescription>
      </Alert>

      {/* Enriched Memories List */}
      <div className="space-y-3">
        {enrichedMemories.length === 0 ? (
          <Card className="bg-zinc-900/50 border-zinc-800">
            <CardContent className="py-8 text-center text-zinc-500">
              No memories found
            </CardContent>
          </Card>
        ) : (
          enrichedMemories.map((memory) => (
            <EnrichedMemoryCard
              key={memory.id}
              memory={memory}
              showComparison={false}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {total > 0 && (
        <MemoryPagination
          currentPage={currentPage}
          totalPages={totalPages}
          itemsPerPage={itemsPerPage}
          total={total}
        />
      )}
    </div>
  );
}
