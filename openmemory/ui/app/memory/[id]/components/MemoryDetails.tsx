"use client";
import { useMemoriesApi, EnrichedMemory } from "@/hooks/useMemoriesApi";
import { MemoryActions } from "./MemoryActions";
import { ArrowLeft, Copy, Check, Network } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRouter } from "next/navigation";
import { AccessLog } from "./AccessLog";
import Image from "next/image";
import Categories from "@/components/shared/categories";
import { useEffect, useState, useCallback } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { constants } from "@/components/shared/source-app";
import { RelatedMemories } from "./RelatedMemories";
import axios from "axios";

interface MemoryDetailsProps {
  memory_id: string;
}

export function MemoryDetails({ memory_id }: MemoryDetailsProps) {
  const router = useRouter();
  const { fetchMemoryById, hasUpdates } = useMemoriesApi();
  const memory = useSelector(
    (state: RootState) => state.memories.selectedMemory
  );
  const userId = useSelector((state: RootState) => state.profile.userId);
  const [copied, setCopied] = useState(false);
  const [enrichedData, setEnrichedData] = useState<Pick<EnrichedMemory, 'entities' | 'relationships' | 'graph_enriched'> | null>(null);
  const [loadingEnrichment, setLoadingEnrichment] = useState(false);

  // Debug: Log component state
  console.log("=== MemoryDetails Component ===");
  console.log("memory_id:", memory_id);
  console.log("userId from store:", userId);
  console.log("memory object:", memory);
  console.log("enrichedData:", enrichedData);
  console.log("loadingEnrichment:", loadingEnrichment);

  const handleCopy = async () => {
    if (memory?.id) {
      await navigator.clipboard.writeText(memory.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const fetchEnrichment = useCallback(async () => {
    if (!userId) {
      console.log("No user_id available for enrichment fetch");
      return;
    }

    console.log("Fetching enrichment for memory:", memory_id, "user:", userId);
    setLoadingEnrichment(true);
    try {
      const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";
      const response = await axios.post(`${URL}/api/v1/memories/filter/enriched`, {
        user_id: userId,
        page: 1,
        size: 100,
      });

      console.log("Enriched response:", response.data);

      // Find the matching memory in the enriched results
      const enriched = response.data.items?.find((item: EnrichedMemory) => item.id === memory_id);
      console.log("Found enriched memory:", enriched);

      if (enriched) {
        setEnrichedData({
          entities: enriched.entities,
          relationships: enriched.relationships,
          graph_enriched: enriched.graph_enriched
        });
        console.log("Set enriched data:", enriched.entities?.length, "entities,", enriched.relationships?.length, "relationships");
      } else {
        console.log("Memory not found in enriched results");
      }
    } catch (error) {
      console.error("Failed to fetch enrichment:", error);
    }
    setLoadingEnrichment(false);
  }, [userId, memory_id]); // Only re-create when userId or memory_id changes

  useEffect(() => {
    console.log("useEffect: Fetching memory by ID:", memory_id);
    fetchMemoryById(memory_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memory_id]); // Only refetch if memory_id changes (which shouldn't happen on this page)

  useEffect(() => {
    console.log("useEffect: Enrichment trigger check");
    console.log("  - userId:", userId);
    console.log("  - memory?.id:", memory?.id);

    if (userId && memory?.id) {
      console.log("  ✓ Conditions met, calling fetchEnrichment");
      fetchEnrichment();
    } else {
      console.log("  ✗ Conditions not met:", {
        hasUserId: !!userId,
        hasMemoryId: !!memory?.id
      });
    }
  }, [userId, memory?.id]); // Only depend on memory.id, not the whole object

  return (
    <div className="container mx-auto py-6 px-4">
      <Button
        variant="ghost"
        className="mb-4 text-zinc-400 hover:text-white"
        onClick={() => router.back()}
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Memories
      </Button>
      <div className="flex gap-4 w-full">
        <div className="rounded-lg w-2/3 border h-fit pb-2 border-zinc-800 bg-zinc-900 overflow-hidden">
          <div className="">
            <div className="flex px-6 py-3 justify-between items-center mb-6 bg-zinc-800 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-white">
                  Memory{" "}
                  <span className="ml-1 text-zinc-400 text-sm font-normal">
                    #{memory?.id?.slice(0, 6)}
                  </span>
                </h1>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 text-zinc-400 hover:text-white -ml-[5px] mt-1"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
              <MemoryActions
                memoryId={memory?.id || ""}
                memoryContent={memory?.text || ""}
                memoryState={memory?.state || ""}
              />
            </div>

            <div className="px-6 py-2">
              <div className="border-l-2 border-primary pl-4 mb-6">
                <p
                  className={`${memory?.state === "archived" || memory?.state === "paused"
                      ? "text-zinc-400"
                      : "text-white"
                    }`}
                >
                  {memory?.text}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-zinc-800">
                <div className="flex justify-between items-center">
                  <div className="">
                    <Categories
                      categories={memory?.categories || []}
                      isPaused={
                        memory?.state === "archived" ||
                        memory?.state === "paused"
                      }
                    />
                  </div>
                  <div className="flex items-center gap-2 min-w-[300px] justify-end">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 bg-zinc-700 px-3 py-1 rounded-lg">
                        <span className="text-sm text-zinc-400">
                          Created by:
                        </span>
                        <div className="w-4 h-4 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                          <Image
                            src={
                              constants[
                                memory?.app_name as keyof typeof constants
                              ]?.iconImage || ""
                            }
                            alt={memory?.app_name || "App"}
                            width={24}
                            height={24}
                          />
                        </div>
                        <p className="text-sm text-zinc-100 font-semibold">
                          {memory?.app_name || "Unknown App"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>


                {/* Graph Enrichment Section */}
                {loadingEnrichment && (
                  <div className="mt-6 pt-4 border-t border-zinc-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Network className="h-4 w-4 text-zinc-500 animate-pulse" />
                      <p className="text-xs text-zinc-500 uppercase">Loading Graph Enrichment...</p>
                    </div>
                  </div>
                )}

                {!loadingEnrichment && enrichedData && enrichedData.graph_enriched && (
                  <div className="mt-6 pt-4 border-t border-zinc-800">
                    <div className="flex items-center gap-2 mb-3">
                      <Network className="h-4 w-4 text-emerald-400" />
                      <p className="text-xs text-zinc-500 uppercase">Graph Enrichment</p>
                      <Badge variant="outline" className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30 text-xs">
                        🕸️ Enriched
                      </Badge>
                    </div>

                    {/* Entities */}
                    {enrichedData.entities && enrichedData.entities.length > 0 && (
                      <div className="mb-4">
                        <p className="text-xs text-zinc-400 mb-2">🏷️ Entities ({enrichedData.entities.length})</p>
                        <div className="flex flex-wrap gap-2">
                          {enrichedData.entities.map((entity, idx) => {
                            const entityTypeColors: Record<string, string> = {
                              PERSON: "bg-blue-500/20 text-blue-300 border-blue-500/30",
                              PLACE: "bg-green-500/20 text-green-300 border-green-500/30",
                              LOCATION: "bg-green-500/20 text-green-300 border-green-500/30",
                              DATE: "bg-purple-500/20 text-purple-300 border-purple-500/30",
                              TIME: "bg-purple-500/20 text-purple-300 border-purple-500/30",
                              ORGANIZATION: "bg-orange-500/20 text-orange-300 border-orange-500/30",
                              EVENT: "bg-pink-500/20 text-pink-300 border-pink-500/30",
                              TECHNOLOGY: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
                              APP: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
                              PROJECT: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
                              CONCEPT: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
                            };
                            const colorClass = entityTypeColors[entity.type] || "bg-zinc-600/20 text-zinc-300 border-zinc-600/30";

                            return (
                              <Badge
                                key={`${entity.name}-${idx}`}
                                variant="outline"
                                className={`${colorClass} text-xs`}
                                title={entity.mentions ? `Mentioned ${entity.mentions} times` : undefined}
                              >
                                {entity.name} <span className="text-xs opacity-70">({entity.type})</span>
                                {entity.mentions && entity.mentions > 1 && (
                                  <span className="ml-1 text-xs opacity-60">×{entity.mentions}</span>
                                )}
                              </Badge>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Relationships */}
                    {enrichedData.relationships && enrichedData.relationships.length > 0 && (
                      <div>
                        <p className="text-xs text-zinc-400 mb-2">🔗 Relationships ({enrichedData.relationships.length})</p>
                        <div className="space-y-2">
                          {enrichedData.relationships.map((rel, idx) => {
                            const relationIcons: Record<string, string> = {
                              HAS_BIRTHDAY: "🎂",
                              WORKS_AT: "💼",
                              LIVES_IN: "🏠",
                              INTERESTED_IN: "⭐",
                              KNOWS: "👥",
                              USES: "🔧",
                              LEARNS: "📚",
                              RELATED_TO: "🔗",
                              WORKS_ON: "💻",
                              PART_OF: "🧩",
                            };
                            const icon = relationIcons[rel.relation] || "→";

                            return (
                              <div
                                key={`${rel.source}-${rel.relation}-${rel.target}-${idx}`}
                                className="bg-zinc-800 rounded-lg px-3 py-2 text-xs"
                              >
                                <span className="text-zinc-300 font-medium">{rel.source}</span>
                                <span className="mx-2 text-zinc-500">{icon}</span>
                                <span className="text-zinc-400 text-xs">{rel.relation.replace(/_/g, " ")}</span>
                                <span className="mx-2 text-zinc-500">→</span>
                                <span className="text-zinc-300 font-medium">{rel.target}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* No enrichment available */}
                {!loadingEnrichment && enrichedData && !enrichedData.graph_enriched && (
                  <div className="mt-6 pt-4 border-t border-zinc-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Network className="h-4 w-4 text-zinc-500" />
                      <p className="text-xs text-zinc-500 uppercase">Graph Enrichment</p>
                    </div>
                    <p className="text-xs text-zinc-500 italic">
                      ❌ No graph enrichment available - memory doesn't contain recognizable entities
                    </p>
                  </div>
                )}

                {/* Debug info - remove after testing */}
                {!loadingEnrichment && !enrichedData && userId && (
                  <div className="mt-6 pt-4 border-t border-zinc-800">
                    <div className="flex items-center gap-2 mb-2">
                      <Network className="h-4 w-4 text-yellow-500" />
                      <p className="text-xs text-yellow-500 uppercase">Debug: Enrichment not loaded</p>
                    </div>
                    <p className="text-xs text-zinc-500">
                      Check browser console for errors. User ID: {userId}
                    </p>
                  </div>
                )}

                {/* Metadata Section */}
                {memory?.metadata_ && Object.keys(memory.metadata_).length > 0 && (
                  <div className="mt-6 pt-4 border-t border-zinc-800">
                    <p className="text-xs text-zinc-500 uppercase mb-3">Metadata</p>
                    <div className="bg-zinc-800 rounded-lg p-4">
                      <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono">
                        {JSON.stringify(memory.metadata_, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {/* <div className="flex justify-end gap-2 w-full mt-2">
                <p className="text-sm font-semibold text-primary my-auto">
                    {new Date(memory.created_at).toLocaleString()}
                  </p>
                </div> */}
              </div>
            </div>
          </div>
        </div>
        <div className="w-1/3 flex flex-col gap-4">
          <AccessLog memoryId={memory?.id || ""} />
          <RelatedMemories memoryId={memory?.id || ""} />
        </div>
      </div>
    </div>
  );
}
