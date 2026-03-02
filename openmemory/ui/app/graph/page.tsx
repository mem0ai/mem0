"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useGraphApi } from "@/hooks/useGraphApi";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Dynamically import GraphVisualization with no SSR
const GraphVisualization = dynamic(
  () => import("./components/GraphVisualization").then((mod) => mod.GraphVisualization),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    ),
  }
);

export default function GraphPage() {
  const { loading, error, graphData, stats, fetchGraphData, fetchGraphStats, searchGraph } =
    useGraphApi();
  const [limit, setLimit] = useState(100);
  const [userId, setUserId] = useState("");

  useEffect(() => {
    // Load initial data
    Promise.all([fetchGraphData(userId || undefined, limit), fetchGraphStats(userId || undefined)]);
  }, []);

  const handleRefresh = async () => {
    await Promise.all([
      fetchGraphData(userId || undefined, limit),
      fetchGraphStats(userId || undefined),
    ]);
  };

  const handleSearch = async (query: string) => {
    await searchGraph(query, userId || undefined);
  };

  const handleLimitChange = async (newLimit: number) => {
    setLimit(newLimit);
    await fetchGraphData(userId || undefined, newLimit);
  };

  return (
    <div className="text-white py-6">
      <div className="container">
        <div className="w-full mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">Memory Graph</h1>
              <p className="text-zinc-400 mt-1">
                Visualize and explore the knowledge graph created by mem0
              </p>
            </div>
            <Button
              onClick={handleRefresh}
              disabled={loading}
              variant="outline"
              className="border-zinc-700 bg-zinc-900 hover:bg-zinc-800"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Refresh
            </Button>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="bg-zinc-900 border-zinc-800 p-4">
                <div className="text-sm text-zinc-400">Total Nodes</div>
                <div className="text-2xl font-bold text-white mt-1">{stats.node_count}</div>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800 p-4">
                <div className="text-sm text-zinc-400">Total Relationships</div>
                <div className="text-2xl font-bold text-white mt-1">
                  {stats.relationship_count}
                </div>
              </Card>
              <Card className="bg-zinc-900 border-zinc-800 p-4">
                <div className="text-sm text-zinc-400">Node Types</div>
                <div className="text-2xl font-bold text-white mt-1">{stats.node_types.length}</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {stats.node_types.slice(0, 3).map((type) => (
                    <span key={type.label} className="text-xs text-zinc-500">
                      {type.label} ({type.count})
                    </span>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Controls */}
          <Card className="bg-zinc-900 border-zinc-800 p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="user-id" className="text-zinc-300">
                  Filter by User ID (optional)
                </Label>
                <Input
                  id="user-id"
                  placeholder="Enter user ID..."
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="limit" className="text-zinc-300">
                  Node Limit: {limit}
                </Label>
                <div className="flex gap-2">
                  <Input
                    id="limit"
                    type="number"
                    min="10"
                    max="1000"
                    step="10"
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="bg-zinc-800 border-zinc-700"
                  />
                  <Button
                    onClick={() => handleLimitChange(limit)}
                    disabled={loading}
                    className="bg-zinc-800 hover:bg-zinc-700"
                  >
                    Apply
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* Error Display */}
          {error && (
            <Card className="bg-red-900/20 border-red-800 p-4">
              <p className="text-red-400">{error}</p>
            </Card>
          )}

          {/* Graph Visualization */}
          <div className="h-[calc(100vh-400px)]">
            <GraphVisualization
              nodes={graphData?.nodes || []}
              relationships={graphData?.relationships || []}
              loading={loading}
              onSearch={handleSearch}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
