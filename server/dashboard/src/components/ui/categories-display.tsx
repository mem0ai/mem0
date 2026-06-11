"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import { createPortal } from "react-dom";

interface CategoriesDisplayProps {
  categories?: string[];
  showAllCategories?: boolean;
}

export function CategoriesDisplay({
  categories,
  showAllCategories,
}: CategoriesDisplayProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState({ top: 0, left: 0 });
  const [isPositioned, setIsPositioned] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isHovered && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPopoverPosition({
        top: rect.bottom + window.scrollY + 8,
        left: rect.left + window.scrollX,
      });
      setIsPositioned(true);
    } else {
      setIsPositioned(false);
    }
  }, [isHovered]);

  const getCategoryColor = (category: string) => {
    const colors = [
      "bg-purple-500",
      "bg-blue-500",
      "bg-green-500",
      "bg-yellow-500",
      "bg-red-500",
      "bg-indigo-500",
      "bg-pink-500",
      "bg-teal-500",
      "bg-orange-500",
      "bg-cyan-500",
    ];

    let hash = 0;
    for (let i = 0; i < category.length; i++) {
      hash = category.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  const allCategories = useMemo(() => {
    return categories || [];
  }, [categories]);

  if (!allCategories || allCategories.length === 0) {
    return <span></span>;
  }

  const firstCategory = allCategories[0];
  const remainingCount = allCategories.length - 1;

  const popoverContent = isHovered &&
    isPositioned &&
    allCategories.length > 1 && (
      <div
        style={{
          position: "fixed",
          top: `${popoverPosition.top}px`,
          left: `${popoverPosition.left}px`,
          zIndex: 999999,
        }}
        className={`p-3 bg-surface-default-tertiary border border-memBorder-primary rounded-lg shadow-xl flex flex-col gap-2.5 min-w-max opacity-100 visible`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Map over all categories to show everything in the popover */}
        {allCategories.map((category, index) => (
          <div
            key={index}
            className="inline-flex items-center gap-1.5 whitespace-nowrap bg-surface-default-fg-secondary border border-memBorder-primary rounded-md px-2 py-1 text-onSurface-default-secondary"
          >
            <div
              className={`size-2 rounded-full ${getCategoryColor(category)}`}
            />
            <span className="typo-body-xs">{category}</span>
          </div>
        ))}
      </div>
    );

  if (showAllCategories) {
    return (
      <div className="relative flex flex-wrap gap-2">
        {allCategories.map((category, index) => (
          <div
            key={index}
            className="inline-flex items-center gap-1.5 whitespace-nowrap bg-surface-default-fg-secondary border border-memBorder-primary rounded-md px-2 py-1 text-onSurface-default-secondary"
          >
            <div
              className={`size-2 rounded-full ${getCategoryColor(category)}`}
            />
            <span className="typo-body-xs">{category}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="relative inline-block">
      <div
        ref={triggerRef}
        className="flex items-center gap-1.5 cursor-pointer"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Always show the first category */}
        <div className="inline-flex items-center gap-1.5 whitespace-nowrap bg-surface-default-fg-secondary border border-memBorder-primary rounded-md px-2 py-1 text-onSurface-default-secondary">
          <div
            className={`size-2 rounded-full ${getCategoryColor(firstCategory)}`}
          />
          <span className="typo-body-xs">{firstCategory}</span>
        </div>

        {/* Show count badge if there are more categories */}
        {remainingCount > 0 && (
          <div className="flex items-center justify-center px-2 py-1.5 typo-body-xs text-onSurface-default-secondary bg-surface-default-fg-secondary border border-memBorder-primary rounded-md">
            +{remainingCount}
          </div>
        )}
      </div>

      {/* Portal-rendered popover */}
      {typeof window !== "undefined" &&
        popoverContent &&
        createPortal(popoverContent, document.body)}
    </div>
  );
}
