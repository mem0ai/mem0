"use client";
import { useEffect } from "react";
import { useSelector, useDispatch } from "react-redux";
import { RootState } from "@/store/store";
import { useAppsApi } from "@/hooks/useAppsApi";
import { AppCard } from "./AppCard";
import { AppCardSkeleton } from "@/skeleton/AppCardSkeleton";
import { AppsPagination } from "./AppsPagination";
import { setPage, App } from "@/store/appsSlice";

export function AppGrid() {
  const dispatch = useDispatch();
  const { fetchApps, isLoading } = useAppsApi();
  const apps = useSelector((state: RootState) => state.apps.apps);
  const filters = useSelector((state: RootState) => state.apps.filters);
  const page = useSelector((state: RootState) => state.apps.page);
  const pageSize = useSelector((state: RootState) => state.apps.pageSize);
  const total = useSelector((state: RootState) => state.apps.total);

  useEffect(() => {
    fetchApps({
      name: filters.searchQuery,
      is_active: filters.isActive === "all" ? undefined : filters.isActive,
      sort_by: filters.sortBy,
      sort_direction: filters.sortDirection,
      page,
      page_size: pageSize,
    });
  }, [fetchApps, filters, page, pageSize]);

  const handlePageChange = (newPage: number) => {
    dispatch(setPage(newPage));
  };

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

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {apps.map((app: App) => (
          <AppCard key={app.id} app={app} />
        ))}
      </div>
      <AppsPagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={handlePageChange}
      />
    </div>
  );
}
