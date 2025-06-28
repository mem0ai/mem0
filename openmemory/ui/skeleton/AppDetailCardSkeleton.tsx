export function AppDetailCardSkeleton() {
  return (
    <div>
      <div className="bg-card border w-full sm:w-[320px] border-border rounded-xl mb-6">
        <div className="flex items-center gap-2 mb-4 bg-muted rounded-t-xl p-3">
          <div className="w-6 h-6 rounded-full bg-muted-foreground/20 animate-pulse" />
          <div className="h-5 w-24 bg-muted-foreground/20 rounded animate-pulse" />
        </div>

        <div className="space-y-4 p-3">
          <div>
            <div className="h-4 w-20 bg-muted rounded mb-2 animate-pulse" />
            <div className="h-5 w-24 bg-muted rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-32 bg-muted rounded mb-2 animate-pulse" />
            <div className="h-5 w-28 bg-muted rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-32 bg-muted rounded mb-2 animate-pulse" />
            <div className="h-5 w-28 bg-muted rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-24 bg-muted rounded mb-2 animate-pulse" />
            <div className="h-5 w-36 bg-muted rounded animate-pulse" />
          </div>

          <div>
            <div className="h-4 w-24 bg-muted rounded mb-2 animate-pulse" />
            <div className="h-5 w-36 bg-muted rounded animate-pulse" />
          </div>

          <hr className="border-border" />

          <div className="flex gap-2 justify-end">
            <div className="h-8 w-[170px] bg-muted rounded animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  )
} 