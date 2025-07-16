"use client";

import { Button } from "@/components/ui/button";
import { HiHome, HiMiniRectangleStack } from "react-icons/hi2";
import { RiApps2AddFill } from "react-icons/ri";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreateMemoryDialog } from "@/app/memories/components/CreateMemoryDialog";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import { Brain, Menu, X, Settings2, Book, Network, Star, User, Info, Heart, BookHeart } from "lucide-react";
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

  // Close mobile menu when route changes
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  // Close mobile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (mobileMenuOpen && !(event.target as Element).closest('header')) {
        setMobileMenuOpen(false);
      }
    };

    if (mobileMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [mobileMenuOpen]);

  // Check for reduced motion preference
  const prefersReducedMotion = typeof window !== 'undefined' && 
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Don't show navbar on landing page or auth page
  if (pathname === "/" || pathname === "/auth") {
    return null;
  }

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === href;
    return pathname.startsWith(href);
  };

  const activeClass = "bg-secondary text-secondary-foreground";
  const inactiveClass = "text-muted-foreground";

  const navLinks = [
    { href: "/dashboard", icon: <HiHome />, label: "Dashboard" },
    { href: "/memories", icon: <HiMiniRectangleStack />, label: "Memories" },
    { href: "/my-life", icon: <BookHeart className="w-4 h-4" />, label: "My Life" },
    { href: "/how-to-use-tools", icon: <Info className="w-4 h-4" />, label: "How to Use" },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center px-4">
        {/* Left Side - Logo */}
        <div className="flex items-center flex-1">
          <Link href="/dashboard" className="flex items-center gap-2">
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
        </div>
        
        {/* Center - Desktop Navigation */}
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
        
        {/* Right Side - Desktop Actions */}
        <div className="hidden md:flex items-center gap-2 flex-1 justify-end">
          {user ? (
            <>
              <Link href="/api-docs">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground"
                >
                  API
                </Button>
              </Link>
              <Link href="/pro">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-purple-500 hover:text-purple-400 flex items-center gap-1"
                >
                  <Star className="w-4 h-4" />
                  Pro
                </Button>
              </Link>
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
              <Link href="/api-docs">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground"
                >
                  API
                </Button>
              </Link>
              <Link href="/pro">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-purple-500 hover:text-purple-400 flex items-center gap-1"
                >
                  <Star className="w-4 h-4" />
                  Pro
                </Button>
              </Link>
              <ThemeToggle />
              <UserNav />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2"
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
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

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && user && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ 
              duration: prefersReducedMotion ? 0 : 0.2,
              ease: "easeInOut"
            }}
            className="md:hidden border-b border-border bg-background/95 backdrop-blur"
          >
            <div className="container px-4 py-4">
              <nav className="flex flex-col gap-2">
                {navLinks.map((link) => (
                  <Link 
                    key={link.href} 
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`w-full justify-start gap-2 ${
                        isActive(link.href) ? activeClass : inactiveClass
                      }`}
                    >
                      {link.icon}
                      {link.label}
                    </Button>
                  </Link>
                ))}
                <div className="pt-2 border-t border-border">
                  <CreateMemoryDialog />
                </div>
              </nav>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
