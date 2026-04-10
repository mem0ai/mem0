"use client";

import { usePathname } from "next/navigation";
import ThemeAwareLogo from "@/components/misc/theme-aware-logo";
import { LinearProgress } from "@/components/ui/linearProgress";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuth } from "@/hooks/use-auth";

export const SIDEBAR_WIDTH = 180;
export const COLLAPSED_SIDEBAR_WIDTH = 64;
export const COLLAPSED_SIDEBAR_PADDING = 16;
export const COLLAPSED_SIDEBAR_WIDTH_WITHOUT_PADDING = COLLAPSED_SIDEBAR_WIDTH - COLLAPSED_SIDEBAR_PADDING;

export const ClientLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const pathname = usePathname();
    const { user, isLoading } = useAuth();

    // Public pages (login, setup) don't need auth check
    const isPublicPage = pathname.startsWith("/login") || pathname.startsWith("/setup");

    if (isLoading && !isPublicPage) {
        return (
            <div className="flex flex-col h-screen w-screen items-center justify-center">
                <ThemeAwareLogo />
                <LinearProgress value={66} className="w-[180px] mt-8 h-1" />
            </div>
        );
    }

    return (
        <TooltipProvider delayDuration={0}>
            {children}
        </TooltipProvider>
    );
};
