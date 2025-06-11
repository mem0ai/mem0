export function AppDetailCardSkeleton() {
  return (
    <div>
      <div className="bg-zinc-900 border w-[320px] border-zinc-800 rounded-xl mb-6">
        <div className="flex items-center gap-2 mb-4 bg-zinc-800 rounded-t-xl p-3">
          <div className="w-6 h-6 rounded-full bg-zinc-700 animate-pulse" />
          <div className="h-5 w-24 bg-zinc-700 rounded animate-pulse" />
        </div>

        <div className="space-y-4 p-3">
          <div>
            <div className="h-4 w-20 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-5 w-24 bg-zinc-800 rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-32 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-5 w-28 bg-zinc-800 rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-32 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-5 w-28 bg-zinc-800 rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-24 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-5 w-36 bg-zinc-800 rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-24 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-5 w-36 bg-zinc-800 rounded animate-pulse" />
          </div>

          <hr className="border-zinc-800" />

          <div className="flex gap-2 justify-end">
            <div className="h-8 w-[170px] bg-zinc-800 rounded animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  )
} 