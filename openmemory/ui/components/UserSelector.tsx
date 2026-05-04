"use client";

import { Check, ChevronsUpDown, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useUsers } from "@/hooks/useUsers";
import { cn } from "@/lib/utils";
import { setUserId } from "@/store/profileSlice";
import { AppDispatch, RootState } from "@/store/store";

const STORAGE_KEY = "openmemory.activeUserId";

/**
 * Combobox that switches the active user_id used by every API call.
 *
 * - Default value comes from NEXT_PUBLIC_USER_ID (the "primary" user the
 *   stack was started with).
 * - The chosen value persists to localStorage and is re-applied on next
 *   page load.
 * - Selecting a value dispatches setUserId on profileSlice — every hook
 *   that reads state.profile.userId re-fetches automatically.
 *
 * Note: the backend endpoints all require user_id, so an "All users" admin
 * view is intentionally not offered here. Multi-user aggregation needs
 * dedicated endpoints; see README_Local.md §"UI UserId facet".
 */
export function UserSelector() {
  const dispatch = useDispatch<AppDispatch>();
  const activeUserId = useSelector((state: RootState) => state.profile.userId);
  const defaultUserId = process.env.NEXT_PUBLIC_USER_ID || "user";

  const { users, isLoading } = useUsers(true);
  const [open, setOpen] = useState(false);

  // On first mount: hydrate from localStorage if it differs from the env default.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== activeUserId) {
      dispatch(setUserId(stored));
    }
    // intentionally only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const choose = (uid: string) => {
    dispatch(setUserId(uid));
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, uid);
    }
    setOpen(false);
  };

  // Always show the active user even if not yet in /api/v1/users (fresh user
  // with zero memories), and the env default at the bottom for quick reset.
  const visible = useMemo(() => {
    const seen = new Set<string>();
    const merged: { user_id: string; memory_count: number; isDefault?: boolean }[] = [];
    for (const u of users) {
      seen.add(u.user_id);
      merged.push({ user_id: u.user_id, memory_count: u.memory_count });
    }
    if (!seen.has(activeUserId)) {
      merged.unshift({ user_id: activeUserId, memory_count: 0 });
      seen.add(activeUserId);
    }
    if (!seen.has(defaultUserId)) {
      merged.push({ user_id: defaultUserId, memory_count: 0, isDefault: true });
    }
    return merged;
  }, [users, activeUserId, defaultUserId]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          role="combobox"
          aria-expanded={open}
          className="flex items-center gap-2 border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800 min-w-[180px] justify-between"
          aria-label={`Active user: ${activeUserId}`}
        >
          <span className="flex items-center gap-2 truncate">
            <Users className="h-4 w-4 opacity-70" />
            <span className="truncate">{activeUserId}</span>
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="end">
        <Command>
          <CommandInput placeholder="Search users…" />
          <CommandList>
            <CommandEmpty>{isLoading ? "Loading…" : "No users found."}</CommandEmpty>
            <CommandGroup heading="Users">
              {visible.map((u) => (
                <CommandItem
                  key={u.user_id}
                  value={u.user_id}
                  onSelect={() => choose(u.user_id)}
                  className="flex items-center justify-between"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Check
                      className={cn(
                        "h-4 w-4",
                        activeUserId === u.user_id ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <span className="truncate">{u.user_id}</span>
                    {u.isDefault && (
                      <span className="text-xs text-zinc-500 ml-1">(default)</span>
                    )}
                  </span>
                  <span className="text-xs text-zinc-500 ml-2">
                    {u.memory_count}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
