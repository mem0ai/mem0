"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface UpgradeBannerProps {
  id: string;
  message: string;
  ctaLabel: string;
  ctaUrl: string;
  variant: "cloud" | "enterprise";
  dismissible?: boolean;
}

export function UpgradeBanner({
  id,
  message,
  ctaLabel,
  ctaUrl,
  variant,
  dismissible = true,
}: UpgradeBannerProps) {
  const [mounted, setMounted] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setDismissed(localStorage.getItem(`nudge_${id}_dismissed`) === "true");
    setMounted(true);
  }, [id]);

  if (!mounted || dismissed) return null;

  const handleDismiss = () => {
    localStorage.setItem(`nudge_${id}_dismissed`, "true");
    setDismissed(true);
  };

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-2.5 rounded-md typo-body-xs font-fustat",
        variant === "cloud"
          ? "bg-memGold-100 border-l-2 border-memGold-500"
          : "bg-memRed-100 border-l-2 border-memRed-400",
      )}
    >
      <p className="flex-1 text-onSurface-default-secondary">{message}</p>
      <a
        href={ctaUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "text-xs font-medium whitespace-nowrap underline",
          variant === "cloud" ? "text-memGold-700" : "text-memRed-600",
        )}
      >
        {ctaLabel}
      </a>
      {dismissible && (
        <button
          onClick={handleDismiss}
          className="p-0.5 rounded hover:bg-surface-default-secondary-hover text-onSurface-default-tertiary"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  );
}
