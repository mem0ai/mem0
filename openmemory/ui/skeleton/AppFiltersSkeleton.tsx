export function AppFiltersSkeleton() {
  return (
    <div className="flex items-center gap-2">
      <div className="relative flex-1">
        <div className="h-9 w-[500px] bg-zinc-800 rounded animate-pulse" />
      </div>
      <div className="h-9 w-[130px] bg-zinc-800 rounded animate-pulse" />
      <div className="h-9 w-[150px] bg-zinc-800 rounded animate-pulse" />
    </div>
  );
} 