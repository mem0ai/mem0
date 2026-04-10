import { cn } from "@/lib/utils"

interface ChartBadgeProps {
  label: string
  color: string
  lite?: boolean
}

export function ChartBadge({ label, color, lite = false }: ChartBadgeProps) {
  return (
    <div className={cn(
      "flex w-fit text-sm items-center gap-2 border rounded-sm border-zinc-300 dark:border-zinc-800",
      lite ? "font-[500] text-[13px] py-0.5 px-2" : "font-semibold py-1 px-2"
    )}>
      <div className="size-3 rounded-full" style={{ backgroundColor: color }}></div>
      <span className="text-zinc-700 dark:text-zinc-300 text-xs">{label}</span>
    </div>
  )
}
