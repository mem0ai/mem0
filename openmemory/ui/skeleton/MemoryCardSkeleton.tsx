export function MemoryCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="p-3 sm:p-4">
        <div className="border-l-2 border-primary pl-3 sm:pl-4 mb-3 sm:mb-4">
          <div className="h-4 w-3/4 bg-muted rounded mb-2 animate-pulse" />
          <div className="h-4 w-1/2 bg-muted rounded animate-pulse" />
        </div>

        <div className="mb-3 sm:mb-4">
          <div className="h-4 w-24 bg-muted rounded mb-2 animate-pulse" />
          <div className="bg-muted rounded p-2 sm:p-3">
            <div className="h-20 w-full bg-muted-foreground/20 rounded animate-pulse" />
          </div>
        </div>

        <div className="mb-2 sm:mb-3">
          <div className="flex gap-2">
            <div className="h-6 w-20 bg-muted rounded-full animate-pulse" />
            <div className="h-6 w-24 bg-muted rounded-full animate-pulse" />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-4 w-32 bg-muted rounded animate-pulse" />
          </div>
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <div className="flex items-center gap-1 bg-muted px-2 sm:px-3 py-1 rounded-lg">
              <div className="h-4 w-20 bg-muted-foreground/20 rounded animate-pulse" />
              <div className="w-4 h-4 sm:w-6 sm:h-6 rounded-full bg-muted-foreground/20 animate-pulse" />
              <div className="h-4 w-24 bg-muted-foreground/20 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 