"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import ThemeAwareLogo from "@/components/misc/theme-aware-logo";
import { LinearProgress } from "@/components/ui/linearProgress";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuth } from "@/hooks/use-auth";

export const SIDEBAR_WIDTH = 180;
export const COLLAPSED_SIDEBAR_WIDTH = 64;
export const COLLAPSED_SIDEBAR_PADDING = 16;
export const COLLAPSED_SIDEBAR_WIDTH_WITHOUT_PADDING =
  COLLAPSED_SIDEBAR_WIDTH - COLLAPSED_SIDEBAR_PADDING;

function AuthLoadingState() {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center">
      <ThemeAwareLogo />
      <LinearProgress value={66} className="mt-8 h-1 w-[180px]" />
    </div>
  );
}

export const ClientLayout: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const isPublicPage =
    pathname.startsWith("/login") || pathname.startsWith("/setup");

  useEffect(() => {
    if (!isPublicPage && !isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, isPublicPage, router, user]);

  if (isLoading && !isPublicPage) {
    return <AuthLoadingState />;
  }

  if (!isPublicPage && !user) {
    return <AuthLoadingState />;
  }

  return <TooltipProvider delayDuration={0}>{children}</TooltipProvider>;
};
