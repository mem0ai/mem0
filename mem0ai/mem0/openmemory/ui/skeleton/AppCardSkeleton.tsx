import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";

export function AppCardSkeleton() {
  return (
    <Card className="bg-zinc-900 text-white border-zinc-800">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-1">
          <div className="relative z-10 rounded-full overflow-hidden bg-zinc-800 w-6 h-6 animate-pulse" />
          <div className="h-7 w-32 bg-zinc-800 rounded animate-pulse" />
        </div>
      </CardHeader>
      <CardContent className="pb-4 my-1">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="h-4 w-24 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-7 w-32 bg-zinc-800 rounded animate-pulse" />
          </div>
          <div>
            <div className="h-4 w-24 bg-zinc-800 rounded mb-2 animate-pulse" />
            <div className="h-7 w-32 bg-zinc-800 rounded animate-pulse" />
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t border-zinc-800 p-0 px-6 py-2 flex justify-between items-center">
        <div className="h-6 w-16 bg-zinc-800 rounded-lg animate-pulse" />
        <div className="h-8 w-28 bg-zinc-800 rounded-lg animate-pulse" />
      </CardFooter>
    </Card>
  );
} 