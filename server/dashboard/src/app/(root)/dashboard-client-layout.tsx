"use client";

import React from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { ClientLayout } from "./clientLayout";
import { Provider } from "react-redux";
import store from "@/store/store";
import { AuthProvider } from "@/lib/auth";
import dynamic from "next/dynamic";

const Toaster = dynamic(
  () =>
    import("@/components/ui/sonner").then((mod) => ({ default: mod.Toaster })),
  {
    ssr: false,
  },
);

export function DashboardClientLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <Provider store={store}>
      <AuthProvider>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <ClientLayout>{children}</ClientLayout>
          <Toaster />
        </ThemeProvider>
      </AuthProvider>
    </Provider>
  );
}
