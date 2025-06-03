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
              
              {/* Discord Link */}
              <a
                href="https://discord.gg/NYru6Wbr"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center"
              >
                <Button
                  variant="outline"
                  size="sm"
                  className="border-indigo-500/50 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 hover:text-indigo-300"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
                  </svg>
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
                    
                    {/* Discord Link - Mobile */}
                    <a
                      href="https://discord.gg/NYru6Wbr"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block"
                    >
                      <Button
                        variant="ghost"
                        className="w-full justify-start gap-2 text-indigo-400 hover:text-indigo-300"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
                        </svg>
                        Join Discord
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
