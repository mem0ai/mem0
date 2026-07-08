export function MemoryCardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
      <div className="p-4">
        <div className="border-l-2 border-primary pl-4 mb-4">
          <div className="h-4 w-3/4 bg-zinc-800 rounded mb-2 animate-pulse" />
          <div className="h-4 w-1/2 bg-zinc-800 rounded animate-pulse" />
        </div>

        <div className="mb-4">
          <div className="h-4 w-24 bg-zinc-800 rounded mb-2 animate-pulse" />
          <div className="bg-zinc-800 rounded p-3">
            <div className="h-20 w-full bg-zinc-700 rounded animate-pulse" />
          </div>
        </div>

        <div className="mb-2">
          <div className="flex gap-2">
            <div className="h-6 w-20 bg-zinc-800 rounded-full animate-pulse" />
            <div className="h-6 w-24 bg-zinc-800 rounded-full animate-pulse" />
          </div>
        </div>

        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="h-4 w-32 bg-zinc-800 rounded animate-pulse" />
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-zinc-800 px-3 py-1 rounded-lg">
              <div className="h-4 w-20 bg-zinc-700 rounded animate-pulse" />
              <div className="w-6 h-6 rounded-full bg-zinc-700 animate-pulse" />
              <div className="h-4 w-24 bg-zinc-700 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 