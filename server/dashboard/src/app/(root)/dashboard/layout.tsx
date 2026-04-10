"use client";

import NavWrapper from "./components/navWrapper";
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
  const isSidebarCollapsed = useSelector((state: RootState) => state.layout.isSidebarCollapsed);

  return (
    <>
      <NavWrapper />
      <div
        className={cn(
          "mt-[48px] rounded-lg relative h-[calc(100vh-56px)] pt-[0] bg-surface-default-primary border border-memBorder-primary overflow-y-auto transition-all ease-in-out font-fustat"
        )}
        style={{
          left: `${isSidebarCollapsed ? COLLAPSED_SIDEBAR_WIDTH : SIDEBAR_WIDTH}px`,
          width: `calc(100vw - ${isSidebarCollapsed ? COLLAPSED_SIDEBAR_WIDTH + 8 : SIDEBAR_WIDTH + 8}px)`
        }}
      >
        <ScrollArea type="scroll" className="h-[calc(100vh-70px)]">
          <div className="mx-auto px-4 py-5 flex-1 flex-col space-y-4 rounded-tl-lg bg-transparent">{children}</div>
        </ScrollArea>
      </div>
    </>
  );
}
