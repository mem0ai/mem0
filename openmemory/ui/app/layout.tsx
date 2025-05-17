import type React from "react";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { Navbar } from "@/components/Navbar";
import { Toaster } from "@/components/ui/toaster";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Providers } from "./providers";
import { AuthProvider } from "../contexts/AuthContext";

export const metadata = {
  title: "Jean Memory - Developer Dashboard",
  description: "Manage your Jean Memory integration and stored memories",
  generator: "v0.dev",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="h-screen font-sans antialiased flex flex-col bg-zinc-950">
        <Providers>
          <AuthProvider>
            <ThemeProvider
              attribute="class"
              defaultTheme="dark"
              enableSystem
              disableTransitionOnChange
            >
              <Navbar />
              <ScrollArea className="h-[calc(100vh-64px)]">{children}</ScrollArea>
              <Toaster />
            </ThemeProvider>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
