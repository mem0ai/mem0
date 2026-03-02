"use client";

import { useEffect, useRef, useState } from "react";
import { InteractiveNvlWrapper, NvlOptions } from "@neo4j-nvl/react";
import { GraphNode, GraphRelationship } from "@/hooks/useGraphApi";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Search, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface GraphVisualizationProps {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  loading?: boolean;
  onSearch?: (query: string) => void;
}

export function GraphVisualization({
  nodes,
  relationships,
  loading = false,
  onSearch,
}: GraphVisualizationProps) {
  const nvlRef = useRef<any>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // Convert our data format to NVL format
  // NVL needs specific caption property for node labels
  const nvlNodes = nodes.map((node) => {
    // Try to find a good caption from properties
    let captionText = node.properties.name ||
                      node.properties.title ||
                      node.properties.user_id ||
                      node.labels[0] ||
                      "Node";

    const captionStr = String(captionText);
    const captionLength = captionStr.length;

    // Calculate node size based on caption length for better visibility
    const baseSize = 30;
    const sizeMultiplier = Math.max(1, Math.min(3, captionLength / 10)); // Scale between 1x and 3x

    // For long captions with underscores, insert newlines to create multi-line text
    // NVL canvas renderer should support \n for line breaks
    const maxLineLength = 15;
    let displayCaption = captionStr;

    if (captionLength > maxLineLength && captionStr.includes('_')) {
      // Split by underscores and rejoin with newlines at appropriate positions
      // Replace underscores with spaces within each segment
      const parts = captionStr.split('_');
      const lines: string[] = [];
      let currentLine = '';

      for (const part of parts) {
        if (!part) continue; // Skip empty parts from consecutive underscores

        const separator = currentLine ? ' ' : '';
        const testLine = currentLine + separator + part;

        if (testLine.length > maxLineLength && currentLine.length > 0) {
          lines.push(currentLine);
          currentLine = part;
        } else {
          currentLine = testLine;
        }
      }

      if (currentLine) {
        lines.push(currentLine);
      }

      displayCaption = lines.join('\n');
    } else if (captionStr.includes('_')) {
      // For shorter captions, just replace underscores with spaces
      displayCaption = captionStr.replace(/_/g, ' ');
    }

    return {
      id: node.id,
      labels: node.labels,
      properties: node.properties,
      caption: displayCaption, // Use newline-separated text
      size: baseSize * sizeMultiplier, // Dynamic size based on text length
    };
  });

  const nvlRelationships = relationships.map((rel) => ({
    id: rel.id,
    from: rel.source,
    to: rel.target,
    type: rel.type,
    properties: rel.properties,
    caption: rel.type, // Show relationship type as label
  }));

  const nvlOptions: NvlOptions = {
    layout: "force",
    initialZoom: 0.8,
    allowDynamicMinZoom: true,
    maxZoom: 3,
    minZoom: 0.05,
    relationshipThreshold: 0.55,
    useWebGL: false,
    instanceId: "graph-viz",
    disableWebGL: true,
    backgroundColor: "#3f3f46",
  };

  const handleNodeClick = (node: any) => {
    const originalNode = nodes.find((n) => n.id === node.id);
    if (originalNode) {
      setSelectedNode(originalNode);
    }
  };

  const handleSearch = () => {
    if (searchQuery && onSearch) {
      onSearch(searchQuery);
    }
  };

  const handleZoomIn = () => {
    if (nvlRef.current) {
      const currentZoom = nvlRef.current.getZoom?.() || 1;
      nvlRef.current.setZoom?.(currentZoom * 1.2);
    }
  };

  const handleZoomOut = () => {
    if (nvlRef.current) {
      const currentZoom = nvlRef.current.getZoom?.() || 1;
      nvlRef.current.setZoom?.(currentZoom * 0.8);
    }
  };

  const handleFitToView = () => {
    if (nvlRef.current) {
      const allNodeIds = nodes.map(n => n.id);
      if (allNodeIds.length > 0) {
        nvlRef.current.zoomToNodes?.(allNodeIds);
      }
    }
  };

  return (
    <div className="flex gap-4 h-full">
      {/* Main Graph Area */}
      <Card className="flex-1 bg-zinc-900 border-zinc-800 relative">
        {/* Search Bar */}
        <div className="absolute top-4 left-4 z-10 flex gap-2">
          <Input
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-64 bg-zinc-800 border-zinc-700"
          />
          <Button
            onClick={handleSearch}
            disabled={!searchQuery || loading}
            size="sm"
            className="bg-zinc-800 hover:bg-zinc-700"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Zoom Controls */}
        <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
          <Button
            onClick={handleZoomIn}
            size="sm"
            variant="outline"
            className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700"
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleZoomOut}
            size="sm"
            variant="outline"
            className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700"
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleFitToView}
            size="sm"
            variant="outline"
            className="bg-zinc-800 border-zinc-700 hover:bg-zinc-700"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Graph Visualization */}
        <div className="w-full h-full min-h-[600px] flex flex-col">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
            </div>
          )}
          {!loading && nodes.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <p className="text-zinc-400">No graph data available</p>
            </div>
          )}
          {!loading && nodes.length > 0 && (
            <>
              <div className="flex-none">
                <p className="text-zinc-300 mb-2">
                  Loaded {nvlNodes.length} nodes, {nvlRelationships.length} relationships
                </p>
                <p className="text-zinc-500 text-xs mb-2">
                  Sample node caption: "{nvlNodes[0]?.caption}"
                </p>
              </div>
              <div className="flex-1 min-h-0" style={{ position: "relative" }}>
                <InteractiveNvlWrapper
                  ref={nvlRef}
                  nodes={nvlNodes}
                  rels={nvlRelationships}
                  nvlOptions={nvlOptions}
                  mouseEventCallbacks={{
                    onNodeClick: handleNodeClick,
                    onPan: () => true, // Enable pan
                    onZoom: () => true, // Enable zoom
                  }}
                />
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Node Details Panel */}
      {selectedNode && (
        <Card className="w-80 bg-zinc-900 border-zinc-800 p-4 overflow-auto">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-white mb-2">Node Details</h3>
              <div className="flex gap-2 flex-wrap">
                {selectedNode.labels.map((label) => (
                  <span
                    key={label}
                    className="px-2 py-1 bg-zinc-800 text-zinc-300 rounded text-xs"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-zinc-400 mb-2">Properties</h4>
              <div className="space-y-2">
                {Object.entries(selectedNode.properties).map(([key, value]) => (
                  <div key={key} className="text-sm">
                    <span className="text-zinc-500">{key}:</span>
                    <span className="text-zinc-300 ml-2 break-words">
                      {typeof value === "object" ? JSON.stringify(value) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <Button
              onClick={() => setSelectedNode(null)}
              variant="outline"
              className="w-full border-zinc-700 hover:bg-zinc-800"
            >
              Close
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
