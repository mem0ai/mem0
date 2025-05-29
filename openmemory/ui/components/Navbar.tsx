"use client";

import { Button } from "@/components/ui/button";
import { HiHome, HiMiniRectangleStack } from "react-icons/hi2";
import { RiApps2AddFill } from "react-icons/ri";
import { FiRefreshCcw } from "react-icons/fi";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreateMemoryDialog } from "@/app/memories/components/CreateMemoryDialog";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import Image from "next/image";
import { useStats } from "@/hooks/useStats";
import { useAppsApi } from "@/hooks/useAppsApi";
import { useAuth } from "@/contexts/AuthContext";
import { Brain, Menu, X, Settings2 } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const memoriesApi = useMemoriesApi();
  const appsApi = useAppsApi();
  const statsApi = useStats();

  // Check for reduced motion preference
  const prefersReducedMotion = typeof window !== 'undefined' && 
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Don't show navbar on landing page
  if (pathname === "/") {
    return null;
  }

  // Define route matchers with typed parameter extraction
  const routeBasedFetchMapping: {
    match: RegExp;
    getFetchers: (params: Record<string, string>) => (() => Promise<any>)[];
  }[] = [
    {
      match: /^\/memory\/([^/]+)$/,
      getFetchers: ({ memory_id }) => [
        () => memoriesApi.fetchMemoryById(memory_id),
        () => memoriesApi.fetchAccessLogs(memory_id),
        () => memoriesApi.fetchRelatedMemories(memory_id),
      ],
    },
    {
      match: /^\/apps\/([^/]+)$/,
      getFetchers: ({ app_id }) => [
        () => appsApi.fetchAppMemories(app_id),
        () => appsApi.fetchAppAccessedMemories(app_id),
        () => appsApi.fetchAppDetails(app_id),
      ],
    },
    {
      match: /^\/memories$/,
      getFetchers: () => [memoriesApi.fetchMemories],
    },
    {
      match: /^\/apps$/,
      getFetchers: () => [appsApi.fetchApps],
    },
    {
      match: /^\/dashboard$/,
      getFetchers: () => [statsApi.fetchStats, memoriesApi.fetchMemories],
    },
    {
      match: /^\/my-life$/,
      getFetchers: () => [memoriesApi.fetchMemories],
    },
  ];

  const getFetchersForPath = (path: string) => {
    for (const route of routeBasedFetchMapping) {
      const match = path.match(route.match);
      if (match) {
        if (route.match.source.includes("memory")) {
          return route.getFetchers({ memory_id: match[1] });
        }
        if (route.match.source.includes("app")) {
          return route.getFetchers({ app_id: match[1] });
        }
        return route.getFetchers({});
      }
    }
    return [];
  };

  const handleRefresh = async () => {
    const fetchers = getFetchersForPath(pathname);
    await Promise.allSettled(fetchers.map((fn) => fn()));
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === href;
    return pathname.startsWith(href);
  };

  const activeClass = "bg-zinc-800 text-white border-zinc-600";
  const inactiveClass = "text-zinc-300";

  const navLinks = [
    { href: "/dashboard", icon: <HiHome />, label: "Dashboard" },
    { href: "/memories", icon: <HiMiniRectangleStack />, label: "Memories" },
    { href: "/my-life", icon: <Brain className="w-4 h-4" />, label: "Life Graph" },
    { href: "/apps", icon: <RiApps2AddFill />, label: "Apps" },
    { href: "/setup-mcp", icon: <Settings2 className="w-4 h-4" />, label: "How to Use" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-800 bg-zinc-950/95 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/60">
      <div className="container flex h-14 items-center justify-between px-4">
        <Link href="/dashboard" className="flex items-center gap-2">
          <Image src="/images/jean-bug.png" alt="Jean Memory" width={26} height={26} />
          <span className="text-lg sm:text-xl font-medium">Jean Memory</span>
        </Link>
        
        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-2">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href}>
              <Button
                variant="outline"
                size="sm"
                className={`flex items-center gap-2 border-none ${
                  isActive(link.href) ? activeClass : inactiveClass
                }`}
              >
                {link.icon}
                {link.label}
              </Button>
            </Link>
          ))}
        </div>
        
        {/* Desktop Actions */}
        <div className="hidden md:flex items-center gap-4">
          {user ? (
            <>
              <Button
                onClick={handleRefresh}
                variant="outline"
                size="sm"
                className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
              >
                <FiRefreshCcw className="transition-transform duration-300 group-hover:rotate-180 motion-reduce:transition-none" />
                Refresh
              </Button>
              <CreateMemoryDialog />
              <Button
                onClick={async () => {
                  await signOut();
                  router.push('/auth');
                }}
                variant="outline"
                size="sm"
                className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800 text-red-400 hover:text-red-300"
              >
                Logout
              </Button>
            </>
          ) : (
            <Link href="/auth">
              <Button
                variant="outline"
                size="sm"
                className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
              >
                Login
              </Button>
            </Link>
          )}
        </div>

        {/* Mobile Menu Button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={prefersReducedMotion ? undefined : { opacity: 0, height: 0 }}
            animate={prefersReducedMotion ? undefined : { opacity: 1, height: "auto" }}
            exit={prefersReducedMotion ? undefined : { opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden border-t border-zinc-800 bg-zinc-950"
          >
            <div className="container px-4 py-4 space-y-2">
              {navLinks.map((link) => (
                <Link key={link.href} href={link.href}>
                  <Button
                    variant="ghost"
                    className={`w-full justify-start gap-2 ${
                      isActive(link.href) ? "bg-zinc-800 text-white" : "text-zinc-300"
                    }`}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {link.icon}
                    {link.label}
                  </Button>
                </Link>
              ))}
              
              <div className="pt-2 border-t border-zinc-800 space-y-2">
                {user ? (
                  <>
                    <Button
                      onClick={handleRefresh}
                      variant="ghost"
                      className="w-full justify-start gap-2"
                    >
                      <FiRefreshCcw className="motion-reduce:transition-none" />
                      Refresh
                    </Button>
                    <CreateMemoryDialog />
                    <Button
                      onClick={async () => {
                        await signOut();
                        router.push('/auth');
                      }}
                      variant="ghost"
                      className="w-full justify-start text-red-400 hover:text-red-300"
                    >
                      Logout
                    </Button>
                  </>
                ) : (
                  <Link href="/auth">
                    <Button
                      variant="ghost"
                      className="w-full justify-start"
                    >
                      Login
                    </Button>
                  </Link>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
