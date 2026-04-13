"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Search } from "lucide-react";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { api } from "@/utils/api";
import { MEMORY_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";

interface SearchResult {
  id: string;
  memory: string;
  score: number;
  user_id?: string;
  agent_id?: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [userId, setUserId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setIsSearching(true);
    setHasSearched(true);
    try {
      const params: Record<string, string> = { query };
      if (userId) params.user_id = userId;
      if (agentId) params.agent_id = agentId;
      const res = await api.post(MEMORY_ENDPOINTS.SEARCH, params);
      setResults(res.data?.results || res.data || []);
    } catch (error: any) {
      toast({
        title: "Search failed",
        description: typeof error === "string" ? error : error?.message,
        variant: "destructive",
      });
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold font-fustat">Search Memories</h1>

      {results.length > 50 && (
        <UpgradeBanner
          id="search-results-50"
          message="Need more precise results? Advanced retrieval available in Cloud."
          ctaLabel="Explore Cloud"
          ctaUrl="https://app.mem0.ai"
          variant="cloud"
        />
      )}

      <div className="flex gap-3">
        <Input
          placeholder="Search your memories..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="flex-1"
        />
        <Input
          placeholder="user_id (optional)"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="w-40"
        />
        <Input
          placeholder="agent_id (optional)"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          className="w-40"
        />
        <Button onClick={handleSearch} disabled={isSearching || !query.trim()}>
          <Search className="size-4 mr-2" />
          Search
        </Button>
      </div>

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((result) => (
            <Card key={result.id} className="border-memBorder-primary">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm flex-1">{result.memory}</p>
                  <span className="text-xs text-onSurface-default-tertiary whitespace-nowrap">
                    {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
                {(result.user_id || result.agent_id) && (
                  <div className="flex gap-3 mt-2 text-xs text-onSurface-default-tertiary">
                    {result.user_id && <span>user: {result.user_id}</span>}
                    {result.agent_id && <span>agent: {result.agent_id}</span>}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {results.length === 0 && hasSearched && !isSearching && (
        <EmptyState
          title={`No results for "${query}"`}
          description="Try a different query or check the user ID."
        />
      )}
    </div>
  );
}
