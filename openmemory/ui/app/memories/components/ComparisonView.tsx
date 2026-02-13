"use client";

import { useState, useEffect } from "react";
import { useMemoriesApi, EnrichedMemory } from "@/hooks/useMemoriesApi";
import { useSearchParams } from "next/navigation";
import { Memory } from "@/components/types";
import { EnrichedMemoryCard } from "@/components/EnrichedMemoryCard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Info, Zap, Network } from "lucide-react";

export function ComparisonView() {
  const searchParams = useSearchParams();
  const { fetchMemories, fetchEnrichedMemories } = useMemoriesApi();
  const [regularMemories, setRegularMemories] = useState<Memory[]>([]);
  const [enrichedMemories, setEnrichedMemories] = useState<EnrichedMemory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentPage = Number(searchParams.get("page")) || 1;
  const itemsPerPage = Number(searchParams.get("size")) || 5; // Smaller for comparison

  useEffect(() => {
    const loadMemories = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const searchQuery = searchParams.get("search") || "";

        // Fetch both regular and enriched in parallel
        const [regularResult, enrichedResult] = await Promise.all([
          fetchMemories(searchQuery, currentPage, itemsPerPage),
          fetchEnrichedMemories(searchQuery, currentPage, itemsPerPage)
        ]);

        setRegularMemories(regularResult.memories);
        setEnrichedMemories(enrichedResult.memories);
      } catch (error: any) {
        console.error("Failed to fetch memories:", error);
        setError(error.message || "Failed to load memories");
      }
      setIsLoading(false);
    };

    loadMemories();
  }, [currentPage, itemsPerPage, searchParams, fetchMemories, fetchEnrichedMemories]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
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
      <Alert className="bg-blue-950/30 border-blue-900/50">
        <Info className="h-4 w-4" />
        <AlertTitle>Comparison Mode</AlertTitle>
        <AlertDescription className="mt-2 space-y-2">
          <p>Side-by-side comparison of regular vs enriched memory queries.</p>
          <div className="flex gap-4 mt-2 text-xs">
            <div className="flex items-center gap-2">
              <Zap className="h-3 w-3 text-yellow-400" />
              <span>Regular: ~10ms query time</span>
            </div>
            <div className="flex items-center gap-2">
              <Network className="h-3 w-3 text-emerald-400" />
              <span>Enriched: ~50-100ms with graph data</span>
            </div>
          </div>
        </AlertDescription>
      </Alert>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Enriched Memories</CardDescription>
            <CardTitle className="text-2xl">{enrichedCount}/{enrichedMemories.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Total Entities</CardDescription>
            <CardTitle className="text-2xl">{totalEntities}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Total Relationships</CardDescription>
            <CardTitle className="text-2xl">{totalRelationships}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Side-by-Side Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Regular Memories */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-400" />
              Regular Query
            </h3>
            <Badge variant="outline" className="bg-yellow-500/20 text-yellow-300 border-yellow-500/30">
              Fast (~10ms)
            </Badge>
          </div>
          <div className="space-y-3">
            {regularMemories.length === 0 ? (
              <Card className="bg-zinc-900/50 border-zinc-800">
                <CardContent className="py-8 text-center text-zinc-500">
                  No memories found
                </CardContent>
              </Card>
            ) : (
              regularMemories.map((memory) => (
                <Card key={memory.id} className="bg-zinc-900/50 border-zinc-800">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium">
                      {memory.memory}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {new Date(memory.created_at).toLocaleString()}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    {memory.categories && memory.categories.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {memory.categories.map((category, idx) => (
                          <Badge key={idx} variant="secondary" className="text-xs">
                            {category}
                          </Badge>
                        ))}
                      </div>
                    )}
                    <div className="mt-3 pt-3 border-t border-zinc-800">
                      <p className="text-xs text-zinc-500 italic">
                        ❌ No entity types or relationships
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </div>

        {/* Enriched Memories */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Network className="h-5 w-5 text-emerald-400" />
              Enriched Query
            </h3>
            <Badge variant="outline" className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">
              With Graph (~50ms)
            </Badge>
          </div>
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
                  showComparison={true}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Explanation */}
      <Alert className="bg-zinc-900/50 border-zinc-800">
        <Info className="h-4 w-4" />
        <AlertTitle>What's the Difference?</AlertTitle>
        <AlertDescription className="mt-2 space-y-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <h4 className="font-semibold text-yellow-400 mb-1">Regular Query</h4>
              <ul className="list-disc list-inside space-y-1 text-zinc-400">
                <li>Fast metadata queries</li>
                <li>Returns content and categories</li>
                <li>No entity type information</li>
                <li>No relationship data</li>
                <li>LLM must infer context from text</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-emerald-400 mb-1">Enriched Query</h4>
              <ul className="list-disc list-inside space-y-1 text-zinc-400">
                <li>Includes Neo4j graph data</li>
                <li>Entity types (Person, Place, Date, etc.)</li>
                <li>Explicit relationships (HAS_BIRTHDAY, WORKS_AT)</li>
                <li>Structured semantic context</li>
                <li>LLM knows exactly what entities mean</li>
              </ul>
            </div>
          </div>
        </AlertDescription>
      </Alert>
    </div>
  );
}
