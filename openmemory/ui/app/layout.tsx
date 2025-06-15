import type React from "react";
import "@/app/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { Navbar } from "@/components/Navbar";
import { Toaster } from "@/components/ui/toaster";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Providers } from "./providers";
import { AuthProvider } from "../contexts/AuthContext";
import type { Metadata } from 'next';
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL('https://jeanmemory.com'),
  title: {
    default: 'Jean Memory - Your Personal Memory Layer',
    template: '%s | Jean Memory',
  },
  description: 'Securely store, manage, and access your digital memories across all your AI applications with Jean Memory.',
  openGraph: {
    title: 'Jean Memory - Your Personal Memory Layer',
    description: 'Securely store, manage, and access your digital memories across all your AI applications.',
    url: 'https://jeanmemory.com',
    siteName: 'Jean Memory',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Jean Memory Banner',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Jean Memory - Your Personal Memory Layer',
    description: 'Securely store, manage, and access your digital memories across all your AI applications.',
    images: ['/og-image.png'],
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased flex flex-col bg-background text-foreground">
        <Providers>
          <AuthProvider>
            <ThemeProvider
              attribute="class"
              defaultTheme="dark"
              enableSystem
              disableTransitionOnChange
            >
              <Navbar />
              <main className="flex-1">
                {children}
              </main>
              <Toaster />
            </ThemeProvider>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
