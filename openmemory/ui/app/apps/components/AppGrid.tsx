"use client";
import { useEffect } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useAppsApi } from "@/hooks/useAppsApi";
import { AppCard } from "./AppCard";
import { SubstackCard } from "./SubstackCard";
import { AppCardSkeleton } from "@/skeleton/AppCardSkeleton";

export function AppGrid() {
  const { fetchApps, isLoading } = useAppsApi();
  const apps = useSelector((state: RootState) => state.apps.apps);
  const filters = useSelector((state: RootState) => state.apps.filters);

  useEffect(() => {
    fetchApps({
      name: filters.searchQuery,
      is_active: filters.isActive === "all" ? undefined : filters.isActive,
      sort_by: filters.sortBy,
      sort_direction: filters.sortDirection,
    });
  }, [fetchApps, filters]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <AppCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (apps.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-8">
        No apps found matching your filters
      </div>
    );
  }

  // Sort apps to ensure Cursor comes first, then Substack, then others
  const sortedApps = [...apps].sort((a, b) => {
    if (a.name === "cursor") return -1;
    if (b.name === "cursor") return 1;
    return 0;
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {sortedApps.map((app) => {
        // Show regular AppCard for all apps
        return <AppCard key={app.id} app={app} />;
      })}
      {/* Add SubstackCard after Cursor (if Cursor exists) */}
      {sortedApps.some(app => app.name === "cursor") && <SubstackCard />}
    </div>
  );
}
