"use client";

import { MainNav } from "./main-nav";
import { PanelRight, LogOut, Settings } from "lucide-react";
import { useCallback } from "react";
import { usePathname } from "next/navigation";
import { COLLAPSED_SIDEBAR_WIDTH, COLLAPSED_SIDEBAR_WIDTH_WITHOUT_PADDING, SIDEBAR_WIDTH } from "../../clientLayout";
import { useDispatch, useSelector } from "react-redux";
import { cn } from "@/lib/utils";
import { toggleSidebar } from "@/store/reducers/layoutReducer";
import { SidebarMenu, SidebarMenuItem, SidebarMenuButton } from "@/components/ui/sidebar";
import { useAuth } from "@/hooks/use-auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Link from "next/link";

export default function NavWrapper() {
  const dispatch = useDispatch();
  const isSidebarCollapsed = useSelector((state: any) => state.layout.isSidebarCollapsed);
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const instanceName = process.env.NEXT_PUBLIC_INSTANCE_NAME || "Mem0";

  const handleToggle = useCallback(() => {
    dispatch(toggleSidebar());
  }, [dispatch]);

  return (
    <div
      className={cn(
        "fixed top-0 left-0 z-30 h-screen flex flex-col transition-all ease-in-out",
        "bg-surface-default-primary"
      )}
      style={{ width: isSidebarCollapsed ? COLLAPSED_SIDEBAR_WIDTH : SIDEBAR_WIDTH }}
    >
      {/* Header */}
      <div className={cn(
        "flex items-center h-[48px] px-3",
        isSidebarCollapsed ? "justify-center" : "justify-between"
      )}>
        {!isSidebarCollapsed && (
          <span className="text-sm font-fustat font-semibold text-onSurface-default-primary truncate">
            {instanceName}
          </span>
        )}
        <button
          onClick={handleToggle}
          className="p-1 rounded hover:bg-surface-default-secondary-hover text-onSurface-default-tertiary"
        >
          <PanelRight className="size-4" />
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto">
        <MainNav />
      </div>

      {/* User menu */}
      <div className="border-t border-memBorder-primary p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  collapsed={isSidebarCollapsed}
                  tooltip={isSidebarCollapsed ? user?.name || "Account" : undefined}
                  className="w-full"
                >
                  <div className="grid size-6 place-items-center rounded-md bg-surface-default-tertiary text-onSurface-default-secondary text-xs font-semibold">
                    {user?.name?.charAt(0).toUpperCase() || "?"}
                  </div>
                  {!isSidebarCollapsed && (
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm truncate">{user?.name}</span>
                      <span className="text-xs text-onSurface-default-tertiary truncate">{user?.email}</span>
                    </div>
                  )}
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top" className="w-56">
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium">{user?.name}</p>
                  <p className="text-xs text-onSurface-default-tertiary">{user?.email}</p>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/dashboard/settings">
                    <Settings className="size-4 mr-2" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="size-4 mr-2" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </div>
    </div>
  );
}
