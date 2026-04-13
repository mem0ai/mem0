"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import { UserRound, Clock9, Bot, AppWindow, SearchIcon } from "lucide-react";
import { EventBadge } from "@/components/shared/event-badge";

interface EntityInfoTagsProps {
  entities: string | string[];
}

const InfoTag = ({
  type,
  value,
  variant = "secondary",
}: {
  type: string;
  value: string;
  variant?: "primary" | "secondary";
}) => {
  const iconMap = {
    User: UserRound,
    Session: Clock9,
    Agent: Bot,
    App: AppWindow,
  };

  if (value === "") {
    return <span className="text-sm">No Entities</span>;
  }

  const Icon = iconMap[type as keyof typeof iconMap] ?? SearchIcon;

  return (
    <EventBadge
      event={type}
      type={type}
      label={value}
      icon={Icon}
      variant={variant}
    />
  );
};

// Helper function to detect entity type from the ID
const detectEntityType = (entityId: string): string => {
  const lowerCase = entityId.toLowerCase();

  // Check if the ID contains type hints
  if (lowerCase.includes("user") || lowerCase.startsWith("u_")) {
    return "User";
  } else if (lowerCase.includes("agent") || lowerCase.startsWith("a_")) {
    return "Agent";
  } else if (
    lowerCase.includes("run") ||
    lowerCase.includes("session") ||
    lowerCase.startsWith("r_")
  ) {
    return "Session";
  } else if (lowerCase.includes("app") || lowerCase.startsWith("app_")) {
    return "App";
  }

  // Default to User for unknown types
  return "User";
};

export function EntityInfoTags({ entities }: EntityInfoTagsProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [showAbove, setShowAbove] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Convert entities to array if it's a string
  const entityArray = useMemo(() => {
    if (Array.isArray(entities)) {
      return entities;
    }
    return [entities];
  }, [entities]);

  // Create tags from entity array
  const allTags = useMemo(() => {
    return entityArray
      .filter((entity) => entity && entity.trim() !== "")
      .map((entity) => ({
        type: detectEntityType(entity),
        value: entity.trim(),
      }));
  }, [entityArray]);

  // Check if we should show popover above to prevent cropping on last row
  useEffect(() => {
    if (isHovered && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      // If less than 200px below, show above instead
      setShowAbove(spaceBelow < 200 && spaceAbove > spaceBelow);
    }
  }, [isHovered]);

  if (allTags.length === 0) {
    return <span className="text-onSurface-default-tertiary"></span>;
  }

  const firstTag = allTags[0];
  const remainingCount = allTags.length - 1;

  return (
    <div
      ref={containerRef}
      className="relative flex min-w-0 items-center gap-1.5"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Always show the first tag – constrain width so long values truncate with ellipsis */}
      <div className="min-w-0 flex-shrink">
        <InfoTag type={firstTag.type} value={firstTag.value} />
      </div>

      {/* Show count badge if there are more tags */}
      {remainingCount > 0 && (
        <EventBadge
          event="remaining"
          type="ADD"
          label={`+${remainingCount}`}
          variant="secondary"
          showIcon={false}
        />
      )}

      {/* Popover revealed on hover */}
      {isHovered && allTags.length > 1 && (
        <div
          className={`absolute left-0 z-10 p-3 bg-surface-default-fg-secondary border border-memBorder-primary rounded-sm shadow-xl flex flex-col gap-2.5 w-max ${
            showAbove ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          {/* We map over allTags to show everything in the popover */}
          {allTags.map((tag, index) => (
            <InfoTag
              key={index}
              type={tag.type}
              value={tag.value}
              variant="primary"
            />
          ))}
        </div>
      )}
    </div>
  );
}
