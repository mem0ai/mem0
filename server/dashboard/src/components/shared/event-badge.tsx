import { Plus, RefreshCw, SearchCode, Trash, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";

interface EventBadgeProps {
  event: string;
  type?: string;
  count?: number;
  label?: string;
  icon?: React.ElementType;
  showIcon?: boolean;
  variant?: "primary" | "secondary";
}

type BadgeVariant = "add" | "update" | "retrieved" | "delete" | "user";

const getBadgeConfig = (
  type: string,
): { variant: BadgeVariant; icon: React.ElementType } => {
  switch (type.toUpperCase()) {
    case "ADD":
      return { variant: "add", icon: Plus };
    case "UPDATE":
      return { variant: "update", icon: RefreshCw };
    case "SEARCH":
    case "GET_ALL":
    case "GET":
      return { variant: "retrieved", icon: SearchCode };
    case "DELETE":
      return { variant: "delete", icon: Trash };
    case "USER":
    case "USERS":
      return { variant: "user", icon: UserRound };
    default:
      return { variant: "add", icon: Plus };
  }
};

export function EventBadge({
  event,
  type,
  count,
  label,
  icon,
  showIcon = true,
  variant = "primary",
}: EventBadgeProps) {
  const resolvedType = (type ?? event).toUpperCase();
  const { variant: badgeVariant, icon: DefaultIcon } =
    getBadgeConfig(resolvedType);
  const Icon = icon ?? DefaultIcon;
  const content = label ?? (typeof count === "number" ? String(count) : "");

  if (count === 0 && !label) {
    return null;
  }

  return (
    <div
      className={cn(
        "inline-flex min-w-0 max-w-full items-center justify-center gap-1 overflow-hidden rounded-sm px-1.5 py-0.5",
        variant === "secondary"
          ? "bg-surface-default-fg-secondary"
          : "bg-surface-default-tertiary",
      )}
      aria-label={`${event} ${badgeVariant} count`}
    >
      {showIcon && (
        <Icon className="size-3.5 shrink-0 text-onSurface-default-secondary" />
      )}
      {content && (
        <span className="min-w-0 truncate font-dm-mono text-xs font-normal leading-[18px] text-onSurface-default-secondary">
          {content}
        </span>
      )}
    </div>
  );
}
