"use client";

import { useEffect, useState } from "react";
import { Filter, X, ChevronDown, SortAsc, SortDesc } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuGroup,
} from "@/components/ui/dropdown-menu";
import { RootState } from "@/store/store";
import { useAppsApi } from "@/hooks/useAppsApi";
import { useFiltersApi } from "@/hooks/useFiltersApi";
import {
  setSelectedApps,
  setSelectedCategories,
  clearFilters,
} from "@/store/filtersSlice";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";

const columns = [
  {
    label: "Memory",
    value: "memory",
  },
  {
    label: "App Name",
    value: "app_name",
  },
  {
    label: "Created On",
    value: "created_at",
  },
];

export default function FilterComponent() {
  const dispatch = useDispatch();
  const { fetchApps } = useAppsApi();
  const { fetchCategories, updateSort } = useFiltersApi();
  const { fetchMemories } = useMemoriesApi();
  const [isOpen, setIsOpen] = useState(false);
  const [tempSelectedApps, setTempSelectedApps] = useState<string[]>([]);
  const [tempSelectedCategories, setTempSelectedCategories] = useState<
    string[]
  >([]);
  const [showArchived, setShowArchived] = useState(false);

  const apps = useSelector((state: RootState) => state.apps.apps);
  const categories = useSelector(
    (state: RootState) => state.filters.categories.items
  );
  const filters = useSelector((state: RootState) => state.filters.apps);

  useEffect(() => {
    fetchApps();
    fetchCategories();
  }, [fetchApps, fetchCategories]);

  useEffect(() => {
    // Initialize temporary selections with current active filters when dialog opens
    if (isOpen) {
      setTempSelectedApps(filters.selectedApps);
      setTempSelectedCategories(filters.selectedCategories);
      setShowArchived(filters.showArchived || false);
    }
  }, [isOpen, filters]);

  useEffect(() => {
    handleClearFilters();
  }, []);

  const toggleAppFilter = (app: string) => {
    setTempSelectedApps((prev) =>
      prev.includes(app) ? prev.filter((a) => a !== app) : [...prev, app]
    );
  };

  const toggleCategoryFilter = (category: string) => {
    setTempSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const toggleAllApps = (checked: boolean) => {
    setTempSelectedApps(checked ? apps.map((app) => app.id) : []);
  };

  const toggleAllCategories = (checked: boolean) => {
    setTempSelectedCategories(checked ? categories.map((cat) => cat.name) : []);
  };

  const handleClearFilters = async () => {
    setTempSelectedApps([]);
    setTempSelectedCategories([]);
    setShowArchived(false);
    dispatch(clearFilters());
    await fetchMemories();
  };

  const handleApplyFilters = async () => {
    try {
      // Get category IDs for selected category names
      const selectedCategoryIds = categories
        .filter((cat) => tempSelectedCategories.includes(cat.name))
        .map((cat) => cat.id);

      // Get app IDs for selected app names
      const selectedAppIds = apps
        .filter((app) => tempSelectedApps.includes(app.id))
        .map((app) => app.id);

      // Update the global state with temporary selections
      dispatch(setSelectedApps(tempSelectedApps));
      dispatch(setSelectedCategories(tempSelectedCategories));
      dispatch({ type: "filters/setShowArchived", payload: showArchived });

      await fetchMemories(undefined, 1, 10, {
        apps: selectedAppIds,
        categories: selectedCategoryIds,
        sortColumn: filters.sortColumn,
        sortDirection: filters.sortDirection,
        showArchived: showArchived,
      });
      setIsOpen(false);
    } catch (error) {
      console.error("Failed to apply filters:", error);
    }
  };

  const handleDialogChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      // Reset temporary selections to active filters when dialog closes without applying
      setTempSelectedApps(filters.selectedApps);
      setTempSelectedCategories(filters.selectedCategories);
      setShowArchived(filters.showArchived || false);
    }
  };

  const setSorting = async (column: string) => {
    const newDirection =
      filters.sortColumn === column && filters.sortDirection === "asc"
        ? "desc"
        : "asc";
    updateSort(column, newDirection);

    // Get category IDs for selected category names
    const selectedCategoryIds = categories
      .filter((cat) => tempSelectedCategories.includes(cat.name))
      .map((cat) => cat.id);

    // Get app IDs for selected app names
    const selectedAppIds = apps
      .filter((app) => tempSelectedApps.includes(app.id))
      .map((app) => app.id);

    try {
      await fetchMemories(undefined, 1, 10, {
        apps: selectedAppIds,
        categories: selectedCategoryIds,
        sortColumn: column,
        sortDirection: newDirection,
      });
    } catch (error) {
      console.error("Failed to apply sorting:", error);
    }
  };

  const hasActiveFilters =
    filters.selectedApps.length > 0 ||
    filters.selectedCategories.length > 0 ||
    filters.showArchived;

  const hasTempFilters =
    tempSelectedApps.length > 0 ||
    tempSelectedCategories.length > 0 ||
    showArchived;

  return (
    <div className="flex items-center gap-2">
      <Dialog open={isOpen} onOpenChange={handleDialogChange}>
        <DialogTrigger asChild>
          <Button
            variant="outline"
            className={`h-9 px-4 border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800 ${
              hasActiveFilters ? "border-primary" : ""
            }`}
          >
            <Filter
              className={`h-4 w-4 ${hasActiveFilters ? "text-primary" : ""}`}
            />
            Filter
            {hasActiveFilters && (
              <Badge className="ml-2 bg-primary hover:bg-primary/80 text-xs">
                {filters.selectedApps.length +
                  filters.selectedCategories.length +
                  (filters.showArchived ? 1 : 0)}
              </Badge>
            )}
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[425px] bg-zinc-900 border-zinc-800 text-zinc-100">
          <DialogHeader>
            <DialogTitle className="text-zinc-100 flex justify-between items-center">
              <span>Filters</span>
            </DialogTitle>
          </DialogHeader>
          <Tabs defaultValue="apps" className="w-full">
            <TabsList className="grid grid-cols-3 bg-zinc-800">
              <TabsTrigger
                value="apps"
                className="data-[state=active]:bg-zinc-700"
              >
                Apps
              </TabsTrigger>
              <TabsTrigger
                value="categories"
                className="data-[state=active]:bg-zinc-700"
              >
                Categories
              </TabsTrigger>
              <TabsTrigger
                value="archived"
                className="data-[state=active]:bg-zinc-700"
              >
                Archived
              </TabsTrigger>
            </TabsList>
            <TabsContent value="apps" className="mt-4">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="select-all-apps"
                    checked={
                      apps.length > 0 && tempSelectedApps.length === apps.length
                    }
                    onCheckedChange={(checked) =>
                      toggleAllApps(checked as boolean)
                    }
                    className="border-zinc-600 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                  />
                  <Label
                    htmlFor="select-all-apps"
                    className="text-sm font-normal text-zinc-300 cursor-pointer"
                  >
                    Select All
                  </Label>
                </div>
                {apps.map((app) => (
                  <div key={app.id} className="flex items-center space-x-2">
                    <Checkbox
                      id={`app-${app.id}`}
                      checked={tempSelectedApps.includes(app.id)}
                      onCheckedChange={() => toggleAppFilter(app.id)}
                      className="border-zinc-600 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                    <Label
                      htmlFor={`app-${app.id}`}
                      className="text-sm font-normal text-zinc-300 cursor-pointer"
                    >
                      {app.name}
                    </Label>
                  </div>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="categories" className="mt-4">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="select-all-categories"
                    checked={
                      categories.length > 0 &&
                      tempSelectedCategories.length === categories.length
                    }
                    onCheckedChange={(checked) =>
                      toggleAllCategories(checked as boolean)
                    }
                    className="border-zinc-600 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                  />
                  <Label
                    htmlFor="select-all-categories"
                    className="text-sm font-normal text-zinc-300 cursor-pointer"
                  >
                    Select All
                  </Label>
                </div>
                {categories.map((category) => (
                  <div
                    key={category.name}
                    className="flex items-center space-x-2"
                  >
                    <Checkbox
                      id={`category-${category.name}`}
                      checked={tempSelectedCategories.includes(category.name)}
                      onCheckedChange={() =>
                        toggleCategoryFilter(category.name)
                      }
                      className="border-zinc-600 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                    />
                    <Label
                      htmlFor={`category-${category.name}`}
                      className="text-sm font-normal text-zinc-300 cursor-pointer"
                    >
                      {category.name}
                    </Label>
                  </div>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="archived" className="mt-4">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="show-archived"
                    checked={showArchived}
                    onCheckedChange={(checked) =>
                      setShowArchived(checked as boolean)
                    }
                    className="border-zinc-600 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                  />
                  <Label
                    htmlFor="show-archived"
                    className="text-sm font-normal text-zinc-300 cursor-pointer"
                  >
                    Show Archived Memories
                  </Label>
                </div>
              </div>
            </TabsContent>
          </Tabs>
          <div className="flex justify-end mt-4 gap-3">
            {/* Clear all button */}
            {hasTempFilters && (
              <Button
                onClick={handleClearFilters}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              >
                Clear All
              </Button>
            )}
            {/* Apply filters button */}
            <Button
              onClick={handleApplyFilters}
              className="bg-primary hover:bg-primary/80 text-white"
            >
              Apply Filters
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="h-9 px-4 border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
          >
            {filters.sortDirection === "asc" ? (
              <SortAsc className="h-4 w-4" />
            ) : (
              <SortDesc className="h-4 w-4" />
            )}
            Sort: {columns.find((c) => c.value === filters.sortColumn)?.label}
            <ChevronDown className="h-4 w-4 ml-2" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56 bg-zinc-900 border-zinc-800 text-zinc-100">
          <DropdownMenuLabel>Sort by</DropdownMenuLabel>
          <DropdownMenuSeparator className="bg-zinc-800" />
          <DropdownMenuGroup>
            {columns.map((column) => (
              <DropdownMenuItem
                key={column.value}
                onClick={() => setSorting(column.value)}
                className="cursor-pointer flex justify-between items-center"
              >
                {column.label}
                {filters.sortColumn === column.value &&
                  (filters.sortDirection === "asc" ? (
                    <SortAsc className="h-4 w-4 text-primary" />
                  ) : (
                    <SortDesc className="h-4 w-4 text-primary" />
                  ))}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
