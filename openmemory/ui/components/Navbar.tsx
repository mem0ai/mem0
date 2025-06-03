"use client";

import { Button } from "@/components/ui/button";
import { HiHome, HiMiniRectangleStack } from "react-icons/hi2";
import { RiApps2AddFill } from "react-icons/ri";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CreateMemoryDialog } from "@/app/memories/components/CreateMemoryDialog";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import { Brain, Menu, X, Settings2 } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Icons } from "@/components/icons";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Check for reduced motion preference
  const prefersReducedMotion = typeof window !== 'undefined' && 
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Don't show navbar on landing page
  if (pathname === "/") {
    return null;
  }

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
              {/* GitHub Repo Link */}
              <a
                href="https://github.com/jonathan-politzki/your-memory"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center"
              >
                <Button
                  variant="outline"
                  size="sm"
                  className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white"
                >
                  <Icons.github className="w-4 h-4" />
                </Button>
              </a>
              
              {/* Pro Link */}
              <a
                href="https://buy.stripe.com/fZuaEX70gev399t4tMabK00"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center"
              >
                <Button
                  variant="outline"
                  size="sm"
                  className="border-purple-500/50 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 hover:text-purple-300 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                  </svg>
                  Pro
                </Button>
              </a>
              
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
                    {/* GitHub Repo Link - Mobile */}
                    <a
                      href="https://github.com/jonathan-politzki/your-memory"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block"
                    >
                      <Button
                        variant="ghost"
                        className="w-full justify-start gap-2 text-zinc-300 hover:text-white"
                      >
                        <Icons.github className="w-4 h-4" />
                      </Button>
                    </a>
                    
                    {/* Pro Link - Mobile */}
                    <a
                      href="https://buy.stripe.com/fZuaEX70gev399t4tMabK00"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block"
                    >
                      <Button
                        variant="ghost"
                        className="w-full justify-start gap-2 text-purple-400 hover:text-purple-300"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                        </svg>
                        Pro
                      </Button>
                    </a>
                    
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
