"use client";

import { useCallback, useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { api } from "@/utils/api";
import { MEMORY_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";

interface Memory {
  id: string;
  memory: string;
  user_id?: string;
  agent_id?: string;
  created_at?: string;
  updated_at?: string;
}

export default function MemoriesPage() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [userId, setUserId] = useState("default_user");
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);

  const fetchMemories = useCallback(async () => {
    if (!userId.trim()) return;
    setIsLoading(true);
    try {
      const res = await api.get(MEMORY_ENDPOINTS.BASE, {
        params: { user_id: userId },
      });
      const data = res.data?.results || res.data || [];
      setMemories(Array.isArray(data) ? data : []);
    } catch {
      toast({ title: "Failed to load memories", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const columns = [
    {
      key: "memory" as keyof Memory,
      label: "Content",
      width: 400,
      render: (value: string) => (
        <span className="line-clamp-2 text-sm">{value}</span>
      ),
    },
    { key: "user_id" as keyof Memory, label: "User", width: 100 },
    { key: "agent_id" as keyof Memory, label: "Agent", width: 100 },
    {
      key: "created_at" as keyof Memory,
      label: "Created",
      width: 120,
      render: (value: string) =>
        value ? new Date(value).toLocaleDateString() : "--",
    },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold font-fustat">Memories</h1>

      {memories.length >= 1000 && (
        <UpgradeBanner
          id="memories-1k"
          message="1,000+ memories stored. Categories can help organize them."
          ctaLabel="Explore Cloud"
          ctaUrl="https://app.mem0.ai"
          variant="cloud"
        />
      )}

      <div className="flex gap-3">
        <Input
          placeholder="User ID"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && fetchMemories()}
          className="w-48"
        />
      </div>

      {isLoading ? (
        <TableSkeleton rows={5} columns={4} />
      ) : memories.length === 0 ? (
        <EmptyState
          title="No memories yet"
          description="Add memories via the API to see them here."
        />
      ) : (
        <DataTable
          data={memories}
          columns={columns}
          getRowKey={(row) => row.id}
          onRowClick={(row) => setSelectedMemory(row)}
        />
      )}

      {selectedMemory && (
        <Card className="border-memBorder-primary">
          <CardContent className="p-4 space-y-2">
            <div className="flex justify-between items-start">
              <p className="text-sm font-medium">Memory Detail</p>
              <button
                onClick={() => setSelectedMemory(null)}
                className="text-xs text-onSurface-default-tertiary hover:underline"
              >
                Close
              </button>
            </div>
            <p className="text-sm">{selectedMemory.memory}</p>
            <div className="flex gap-4 text-xs text-onSurface-default-tertiary">
              <span>ID: {selectedMemory.id}</span>
              {selectedMemory.user_id && (
                <span>User: {selectedMemory.user_id}</span>
              )}
              {selectedMemory.agent_id && (
                <span>Agent: {selectedMemory.agent_id}</span>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
