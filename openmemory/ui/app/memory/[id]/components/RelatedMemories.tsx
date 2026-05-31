import { useEffect, useState } from "react";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { Memory } from "@/components/types";
import Categories from "@/components/shared/categories";
import Link from "next/link";
import { formatDate } from "@/lib/helpers";
interface RelatedMemoriesProps {
  memoryId: string;
}

export function RelatedMemories({ memoryId }: RelatedMemoriesProps) {
  const { fetchRelatedMemories } = useMemoriesApi();
  const relatedMemories = useSelector(
    (state: RootState) => state.memories.relatedMemories
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadRelatedMemories = async () => {
      try {
        await fetchRelatedMemories(memoryId);
      } catch (error) {
        console.error("Failed to fetch related memories:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadRelatedMemories();
  }, []);

  if (isLoading) {
    return (
      <div className="w-full max-w-2xl mx-auto rounded-lg overflow-hidden bg-zinc-900 text-white p-6">
        <p className="text-center text-zinc-500">Loading related memories...</p>
      </div>
    );
  }

  if (!relatedMemories.length) {
    return (
      <div className="w-full max-w-2xl mx-auto rounded-lg overflow-hidden bg-zinc-900 text-white p-6">
        <p className="text-center text-zinc-500">No related memories found</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800 text-white">
      <div className="px-6 py-4 flex justify-between items-center bg-zinc-800 border-b border-zinc-800">
        <h2 className="font-semibold">Related Memories</h2>
      </div>
      <div className="space-y-6 p-6">
        {relatedMemories.map((memory: Memory) => (
          <div
            key={memory.id}
            className="border-l-2 border-zinc-800 pl-6 py-1 hover:bg-zinc-700/10 transition-colors cursor-pointer"
          >
            <Link href={`/memory/${memory.id}`}>
              <h3 className="font-medium mb-3">{memory.memory}</h3>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Categories
                    categories={memory.categories}
                    isPaused={
                      memory.state === "paused" || memory.state === "archived"
                    }
                    concat={true}
                  />
                  {memory.state !== "active" && (
                    <span className="inline-block px-3 border border-yellow-600 text-yellow-600 font-semibold text-xs rounded-full bg-yellow-400/10 backdrop-blur-sm">
                      {memory.state === "paused" ? "Paused" : "Archived"}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-zinc-400 text-sm">
                    {formatDate(memory.created_at)}
                  </div>
                </div>
              </div>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
