import { EnrichedMemory } from "@/hooks/useMemoriesApi";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface EnrichedMemoryCardProps {
  memory: EnrichedMemory;
  showComparison?: boolean;
}

const entityTypeColors: Record<string, string> = {
  PERSON: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  PLACE: "bg-green-500/20 text-green-300 border-green-500/30",
  DATE: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  ORGANIZATION: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  EVENT: "bg-pink-500/20 text-pink-300 border-pink-500/30",
  CONCEPT: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  TECHNOLOGY: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  default: "bg-zinc-500/20 text-zinc-300 border-zinc-500/30"
};

const relationshipIcons: Record<string, string> = {
  HAS_BIRTHDAY: "🎂",
  WORKS_AT: "💼",
  LIVES_IN: "🏠",
  INTERESTED_IN: "⭐",
  KNOWS: "👥",
  USES: "🔧",
  LEARNS: "📚",
  RELATED_TO: "🔗",
  default: "→"
};

export function EnrichedMemoryCard({ memory, showComparison = false }: EnrichedMemoryCardProps) {
  const hasGraphData = memory.graph_enriched && (memory.entities?.length || memory.relationships?.length);

  return (
    <Card className="bg-zinc-900/50 border-zinc-800">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-sm font-medium">
              {memory.memory}
            </CardTitle>
            <CardDescription className="text-xs mt-1">
              {new Date(memory.created_at).toLocaleString()}
            </CardDescription>
          </div>
          {hasGraphData && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge variant="outline" className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30">
                    🕸️ Enriched
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Contains graph data (entities & relationships)</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Categories */}
        {memory.categories && memory.categories.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {memory.categories.map((category, idx) => (
              <Badge key={idx} variant="secondary" className="text-xs">
                {category}
              </Badge>
            ))}
          </div>
        )}

        {/* Graph Enrichment Section */}
        {hasGraphData && (
          <div className="mt-4 space-y-3 pt-3 border-t border-zinc-800">
            {/* Entities */}
            {memory.entities && memory.entities.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-400 mb-2 flex items-center gap-2">
                  <span>🏷️ Entities</span>
                  <span className="text-zinc-600">({memory.entities.length})</span>
                </h4>
                <div className="flex flex-wrap gap-2">
                  {memory.entities.map((entity, idx) => (
                    <TooltipProvider key={idx}>
                      <Tooltip>
                        <TooltipTrigger>
                          <Badge
                            variant="outline"
                            className={entityTypeColors[entity.type] || entityTypeColors.default}
                          >
                            <span className="font-medium">{entity.name}</span>
                            <span className="ml-1 text-xs opacity-70">({entity.type})</span>
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="text-xs">
                            <p className="font-semibold">{entity.name}</p>
                            <p className="text-zinc-400">Type: {entity.label}</p>
                            {entity.properties && Object.keys(entity.properties).length > 0 && (
                              <div className="mt-1 pt-1 border-t border-zinc-700">
                                {Object.entries(entity.properties).slice(0, 3).map(([key, value]) => (
                                  <p key={key} className="text-zinc-500">
                                    {key}: {String(value)}
                                  </p>
                                ))}
                              </div>
                            )}
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  ))}
                </div>
              </div>
            )}

            {/* Relationships */}
            {memory.relationships && memory.relationships.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-400 mb-2 flex items-center gap-2">
                  <span>🔗 Relationships</span>
                  <span className="text-zinc-600">({memory.relationships.length})</span>
                </h4>
                <div className="space-y-2">
                  {memory.relationships.slice(0, 5).map((rel, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 text-xs bg-zinc-800/50 rounded px-2 py-1.5"
                    >
                      <Badge variant="outline" className="bg-blue-500/20 text-blue-300 border-blue-500/30">
                        {rel.source}
                      </Badge>
                      <span className="flex items-center gap-1 text-zinc-500">
                        <span>{relationshipIcons[rel.relation] || relationshipIcons.default}</span>
                        <span className="font-mono text-[10px]">{rel.relation}</span>
                      </span>
                      <Badge variant="outline" className="bg-green-500/20 text-green-300 border-green-500/30">
                        {rel.target}
                      </Badge>
                    </div>
                  ))}
                  {memory.relationships.length > 5 && (
                    <p className="text-xs text-zinc-500 italic">
                      +{memory.relationships.length - 5} more relationships
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* No graph data indicator */}
        {!hasGraphData && showComparison && (
          <div className="mt-4 pt-3 border-t border-zinc-800">
            <p className="text-xs text-zinc-500 italic">
              No graph enrichment data available
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
