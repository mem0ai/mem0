import * as React from "react";

import { cn } from "@/lib/utils";

interface PillTab<T extends string> {
  key: T;
  label: string;
  icon?: React.ReactNode;
}

interface PillTabsProps<T extends string> {
  tabs: PillTab<T>[];
  selected: T;
  onSelect: (key: T) => void;
  className?: string;
}

function PillTabs<T extends string>({
  tabs,
  selected,
  onSelect,
  className,
}: PillTabsProps<T>) {
  return (
    <div
      role="tablist"
      className={cn(
        "inline-flex items-center rounded-xl bg-surface-default-secondary p-1 gap-1",
        className,
      )}
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          aria-selected={selected === tab.key}
          onClick={() => onSelect(tab.key)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-onSurface-default-tertiary focus-visible:ring-offset-1",
            selected === tab.key
              ? "bg-surface-default-primary dark:bg-surface-default-tertiary text-onSurface-default-primary shadow-sm"
              : "text-onSurface-default-tertiary hover:text-onSurface-default-secondary",
          )}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
}

PillTabs.displayName = "PillTabs";

export { PillTabs };
export type { PillTab, PillTabsProps };
