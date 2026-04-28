"use client";

import Image from "next/image";
import { useTheme } from "next-themes";

interface EmptyStateProps {
  title: string;
  description?: string;
  image?: "memories" | "requests";
  children?: React.ReactNode;
}

export function EmptyState({
  title,
  description,
  image = "memories",
  children,
}: EmptyStateProps) {
  const { resolvedTheme } = useTheme();
  const src =
    resolvedTheme === "dark"
      ? `/images/no-${image}-dark.svg`
      : `/images/no-${image}.svg`;

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Image
        src={src}
        alt=""
        width={120}
        height={120}
        className="mb-4 opacity-80"
      />
      <p className="text-sm font-medium text-onSurface-default-primary">
        {title}
      </p>
      {description && (
        <p className="text-xs text-onSurface-default-tertiary mt-1 max-w-xs">
          {description}
        </p>
      )}
      {children}
    </div>
  );
}
