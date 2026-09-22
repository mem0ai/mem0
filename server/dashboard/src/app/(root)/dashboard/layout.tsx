"use client";

import NavWrapper from "./components/nav-wrapper";
import { cn } from "@/lib/utils";
import { SIDEBAR_WIDTH, COLLAPSED_SIDEBAR_WIDTH } from "../clientLayout";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const isSidebarCollapsed = useSelector(
    (state: RootState) => state.layout.isSidebarCollapsed,
  );

  return (
    <>
      <NavWrapper />
      <div
        className="mt-[48px] rounded-tl-lg relative h-[calc(100vh-56px)] bg-surface-default-primary border border-memBorder-primary overflow-hidden transition-all duration-300 ease-in-out font-fustat"
        style={{
          left: `${isSidebarCollapsed ? COLLAPSED_SIDEBAR_WIDTH : SIDEBAR_WIDTH}px`,
          width: `calc(100vw - ${isSidebarCollapsed ? COLLAPSED_SIDEBAR_WIDTH + 8 : SIDEBAR_WIDTH + 8}px)`,
        }}
      >
        <ScrollArea type="scroll" className="h-[calc(100vh-70px)]">
          <div className="mx-auto px-6 py-6 flex-1 flex-col space-y-4">
            {children}
          </div>
        </ScrollArea>
      </div>
    </>
  );
}
