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
import SourceApp from "@/components/shared/source-app";

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

export default function FilterComponent({ onFilterChange }: { onFilterChange: () => void }) {
  const dispatch = useDispatch();
  const { fetchApps } = useAppsApi();
  const { fetchCategories, updateSort } = useFiltersApi();
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
    await onFilterChange();
  };

  const handleApplyFilters = async () => {
    try {
      // Use category names directly instead of converting to IDs
      // The backend expects category names, not IDs
      const selectedCategoryNames = tempSelectedCategories;

      // Update the global state with temporary selections
      dispatch(setSelectedApps(tempSelectedApps));
      dispatch(setSelectedCategories(selectedCategoryNames));
      dispatch({ type: "filters/setShowArchived", payload: showArchived });

      await onFilterChange();
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

    try {
      await onFilterChange();
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
            className={`h-9 px-4 ${
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
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="flex justify-between items-center">
              <span>Filters</span>
            </DialogTitle>
          </DialogHeader>
          <Tabs defaultValue="apps" className="w-full">
            <TabsList className="grid grid-cols-3">
              <TabsTrigger
                value="apps"
              >
                Apps
              </TabsTrigger>
              <TabsTrigger
                value="categories"
              >
                Categories
              </TabsTrigger>
              <TabsTrigger
                value="archived"
              >
                Archived
              </TabsTrigger>
            </TabsList>
            <TabsContent value="apps" className="mt-4">
              <div className="max-h-64 overflow-y-auto">
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
                        className="text-sm font-normal text-zinc-300 cursor-pointer flex-1"
                      >
                        <SourceApp source={app.name} />
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>
            <TabsContent value="categories" className="mt-4">
              <div className="max-h-64 overflow-y-auto">
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
                        className="text-sm font-normal text-zinc-300 cursor-pointer flex-1"
                      >
                        {category.name || category.id || 'Unknown Category'}
                      </Label>
                    </div>
                  ))}
                </div>
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
                variant="ghost"
              >
                Clear All
              </Button>
            )}
            {/* Apply filters button */}
            <Button
              onClick={handleApplyFilters}
            >
              Apply Filters
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="h-9 px-4">
            {filters.sortDirection === "asc" ? (
              <SortAsc className="h-4 w-4" />
            ) : (
              <SortDesc className="h-4 w-4" />
            )}
            <span className="ml-2">
              Sort:{" "}
              {columns.find((c) => c.value === filters.sortColumn)?.label ||
                "Created On"}
            </span>
            <ChevronDown className="h-4 w-4 ml-2" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Sort by</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            {columns.map((column) => (
              <DropdownMenuItem
                key={column.value}
                onClick={() => setSorting(column.value)}
                className="cursor-pointer"
              >
                {column.label}
                {filters.sortColumn === column.value && (
                  <>
                    {filters.sortDirection === "asc" ? (
                      <SortAsc className="h-4 w-4 ml-auto" />
                    ) : (
                      <SortDesc className="h-4 w-4 ml-auto" />
                    )}
                  </>
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
