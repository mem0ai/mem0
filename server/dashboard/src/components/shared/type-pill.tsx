import { cn } from "@/lib/utils"

type TypePillVariant = "add" | "update" | "delete" | "search" | "get" | "default"

interface TypePillProps {
  value: string
  className?: string
}

const getTypeVariant = (type: string): TypePillVariant => {
  const normalizedType = type.trim().toUpperCase().replace(/\s+/g, "_")

  if (normalizedType.includes("DELETE")) {
    return "delete"
  }
  if (normalizedType.includes("UPDATE")) {
    return "update"
  }
  if (normalizedType === "GET" || normalizedType.includes("GET_")) {
    return "get"
  }
  if (normalizedType.includes("SEARCH")) {
    return "search"
  }
  if (normalizedType.includes("ADD")) {
    return "add"
  }
  return "default"
}

const getTypeLabel = (type: string) => type.replace(/_/g, " ")

export function TypePill({ value, className }: TypePillProps) {
  const variant = getTypeVariant(value)
  const baseClasses =
    "inline-flex items-center justify-center gap-1 rounded-sm px-1.5 py-0.5 font-dm-mono text-xs font-medium leading-4 tracking-[0.6px] uppercase"

  const variantClasses: Record<TypePillVariant, string> = {
    add: "bg-surface-event-add text-onSurface-event-add",
    update: "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
    delete: "bg-surface-event-delete text-onSurface-event-delete",
    search: "bg-surface-event-search text-onSurface-event-search",
    get: "bg-surface-event-get text-onSurface-event-get",
    default: "bg-surface-event-search text-onSurface-event-search",
  }

  return (
    <span className={cn(baseClasses, variantClasses[variant], className)}>
      {getTypeLabel(value)}
    </span>
  )
}
