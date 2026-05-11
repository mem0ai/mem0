import "@/styles/globals.css";
import { cn } from "@/lib/utils";
import { Inter, InterDisplay, Roboto, Fustat, DMMono } from "./fonts";
import { PublicRuntimeConfigScript } from "@/components/public-runtime-config-script";
import { Metadata } from "next";
import { DashboardClientLayout } from "./dashboard-client-layout";

export const metadata: Metadata = {
  title: "Dashboard | Mem0",
  description: "Mem0 Dashboard",
};

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn(
        Fustat.variable,
        InterDisplay.variable,
        Inter.variable,
        Roboto.variable,
        DMMono.variable,
      )}
      suppressHydrationWarning
    >
      <body
        className={cn(
          Inter.className,
          InterDisplay.variable,
          Roboto.variable,
          Fustat.variable,
          DMMono.variable,
        )}
        suppressHydrationWarning
      >
        <PublicRuntimeConfigScript />
        <DashboardClientLayout>{children}</DashboardClientLayout>
      </body>
    </html>
  );
}
