"use client";

import { Button } from "@/components/ui/button";
import { HiHome, HiMiniRectangleStack } from "react-icons/hi2";
import { RiApps2AddFill } from "react-icons/ri";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreateMemoryDialog } from "@/app/memories/components/CreateMemoryDialog";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import { Brain, Menu, X, Settings2, Book, Network } from "lucide-react";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Icons } from "@/components/icons";
import { UserNav } from "./UserNav";
import { ThemeToggle } from "./ThemeToggle";
import { useTheme } from "next-themes";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Check for reduced motion preference
  const prefersReducedMotion = typeof window !== 'undefined' && 
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Don't show navbar on landing page
  if (pathname === "/") {
    return null;
  }

  const isActive = (href: string) => {
    if (href === "/dashboard-new") return pathname === href || pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  const activeClass = "bg-secondary text-secondary-foreground";
  const inactiveClass = "text-muted-foreground";

  const navLinks = [
    { href: "/dashboard-new", icon: <HiHome />, label: "Dashboard" },
    { href: "/memories", icon: <HiMiniRectangleStack />, label: "Memories" },
    { href: "/my-life", icon: <Network className="w-4 h-4" />, label: "Life Graph" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between px-4">
        <Link href="/dashboard-new" className="flex items-center gap-2">
          {mounted ? (
            <Image
              src={
                theme === "light"
                  ? "/images/jean-white-theme-bug.png"
                  : "/images/jean-bug.png"
              }
              alt="Jean Memory"
              width={26}
              height={26}
            />
          ) : (
            <div style={{ width: 26, height: 26 }} />
          )}
          <span className="text-lg sm:text-xl font-medium">Jean</span>
        </Link>
        
        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-2">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href}>
              <Button
                variant="ghost"
                size="sm"
                className={`flex items-center gap-2 ${
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
        <div className="hidden md:flex items-center gap-2">
          {user ? (
            <>
              <CreateMemoryDialog />
              <ThemeToggle />
              <UserNav />
            </>
          ) : (
            <Link href="/auth">
              <Button>
                Login
              </Button>
            </Link>
          )}
        </div>

        {/* Mobile Actions */}
        <div className="flex items-center gap-2 md:hidden">
          {user ? (
            <>
              <ThemeToggle />
              <UserNav />
            </>
          ) : (
            <Link href="/auth">
              <Button>
                Login
              </Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
