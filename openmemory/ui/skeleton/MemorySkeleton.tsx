import { Skeleton } from "@/components/ui/skeleton";

export function MemorySkeleton() {
  return (
    <div className="container mx-auto py-8 px-4">
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <Skeleton className="h-8 w-48 bg-zinc-800" />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-24 bg-zinc-800" />
              <Skeleton className="h-8 w-24 bg-zinc-800" />
            </div>
          </div>

          <div className="border-l-2 border-zinc-800 pl-4 mb-6">
            <Skeleton className="h-6 w-full bg-zinc-800" />
          </div>

          <div className="mt-6 pt-6 border-t border-zinc-800">
            <Skeleton className="h-4 w-48 bg-zinc-800" />
          </div>
        </div>
      </div>
    </div>
  );
} 