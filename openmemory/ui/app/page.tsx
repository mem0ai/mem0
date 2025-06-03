"use client";

import { useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Shield, Zap, Globe } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import AnimatedSphere from "@/components/landing/AnimatedSphere";
import AnimatedIcons from "@/components/landing/AnimatedIcons";
import MouseFollowArrow from "@/components/landing/MouseFollowArrow";
import { useAuth } from "@/contexts/AuthContext";

export default function LandingPage() {
  const buttonRef = useRef<HTMLAnchorElement>(null);
  const router = useRouter();
  const { user, isLoading } = useAuth();

  // Redirect authenticated users to dashboard immediately
  useEffect(() => {
    if (!isLoading && user) {
      console.log('Landing page: User authenticated, redirecting to dashboard');
      router.replace('/dashboard');
    }
  }, [user, isLoading, router]);

  // Also check for Supabase OAuth callback and redirect immediately
  useEffect(() => {
    // Check if this is a Supabase OAuth callback (has access_token or code in URL)
    const urlParams = new URLSearchParams(window.location.search);
    const hashParams = new URLSearchParams(window.location.hash.substring(1));
    
    if (urlParams.get('code') || hashParams.get('access_token')) {
      console.log('Landing page: OAuth callback detected, will redirect to dashboard once auth completes');
      // Don't render the landing page content if this is an OAuth callback
      return;
    }
  }, []);

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  // Don't render landing page for authenticated users (they'll be redirected)
  if (user) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Redirecting to dashboard...</div>
      </div>
    );
  }

  // Check if this is an OAuth callback - show loading instead of landing page
  const urlParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.substring(1));
  
  if (urlParams.get('code') || hashParams.get('access_token')) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Completing authentication...</div>
      </div>
    );
  }

  // Show landing page for unauthenticated users
  return (
    <div className="relative min-h-screen bg-black text-white overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <ParticleNetwork />
      </div>
      <AnimatedSphere />
      <AnimatedIcons />

      {/* Mouse Follow Arrow */}
      <MouseFollowArrow targetRef={buttonRef} />

      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-purple-900/20 via-transparent to-blue-900/20" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/50 to-black" />

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-4xl mx-auto w-full"
        >
          {/* Logo/Title */}
          <motion.h1
            className="text-5xl sm:text-6xl md:text-8xl font-bold mb-4 sm:mb-6 bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            Jean Memory
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="text-lg sm:text-xl md:text-2xl text-gray-300 mb-8 sm:mb-12 max-w-2xl mx-auto px-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            Your secure, unified memory layer across all AI applications
          </motion.p>

          {/* GitHub Badges */}
          <motion.div
            className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mb-8 sm:mb-12"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            <a 
              href="https://github.com/jonathan-politzki/your-memory" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:scale-105 transition-transform duration-200"
            >
              <img 
                src="https://img.shields.io/github/stars/jonathan-politzki/your-memory?style=social" 
                alt="GitHub stars"
                className="h-5 sm:h-6"
              />
            </a>
            <a 
              href="https://github.com/jonathan-politzki/your-memory/fork" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:scale-105 transition-transform duration-200"
            >
              <img 
                src="https://img.shields.io/github/forks/jonathan-politzki/your-memory?style=social" 
                alt="GitHub forks"
                className="h-5 sm:h-6"
              />
            </a>
            <a 
              href="https://github.com/jonathan-politzki/your-memory/blob/main/LICENSE" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:scale-105 transition-transform duration-200"
            >
              <img 
                src="https://img.shields.io/github/license/jonathan-politzki/your-memory?style=flat-square&color=blue" 
                alt="License"
                className="h-5 sm:h-6"
              />
            </a>
            <a 
              href="https://github.com/jonathan-politzki/your-memory/commits/main" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:scale-105 transition-transform duration-200"
            >
              <img 
                src="https://img.shields.io/github/last-commit/jonathan-politzki/your-memory?style=flat-square&color=green" 
                alt="Last commit"
                className="h-5 sm:h-6"
              />
            </a>
            <a 
              href="https://github.com/jonathan-politzki/your-memory/issues" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:scale-105 transition-transform duration-200"
            >
              <img 
                src="https://img.shields.io/github/issues/jonathan-politzki/your-memory?style=flat-square&color=orange" 
                alt="GitHub issues"
                className="h-5 sm:h-6"
              />
            </a>
          </motion.div>

          {/* Features */}
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-8 sm:mb-12 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-4 sm:p-6 border border-white/10">
              <Shield className="w-6 h-6 sm:w-8 sm:h-8 text-purple-400 mb-2 sm:mb-3 mx-auto" />
              <h3 className="text-base sm:text-lg font-semibold mb-1 sm:mb-2">Secure & Private</h3>
              <p className="text-xs sm:text-sm text-gray-400">Your memories stay yours with end-to-end encryption</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-4 sm:p-6 border border-white/10">
              <Zap className="w-6 h-6 sm:w-8 sm:h-8 text-blue-400 mb-2 sm:mb-3 mx-auto" />
              <h3 className="text-base sm:text-lg font-semibold mb-1 sm:mb-2">Lightning Fast</h3>
              <p className="text-xs sm:text-sm text-gray-400">Instant access to your context across all AI tools</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-4 sm:p-6 border border-white/10">
              <Globe className="w-6 h-6 sm:w-8 sm:h-8 text-cyan-400 mb-2 sm:mb-3 mx-auto" />
              <h3 className="text-base sm:text-lg font-semibold mb-1 sm:mb-2">Universal</h3>
              <p className="text-xs sm:text-sm text-gray-400">Works with Claude, GPT, Gemini, and more</p>
            </div>
          </motion.div>

          {/* Discord Community Section */}
          <motion.div
            className="bg-indigo-500/10 backdrop-blur-sm rounded-lg p-4 sm:p-6 border border-indigo-500/20 mb-8 sm:mb-12 max-w-lg mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.7 }}
          >
            <div className="flex items-center justify-center gap-3 mb-3">
              <svg className="w-6 h-6 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
              </svg>
              <h3 className="text-base sm:text-lg font-semibold text-indigo-300">Join Our Community</h3>
            </div>
            <p className="text-xs sm:text-sm text-gray-400 mb-4 text-center">
              Connect with fellow users, get support, and shape the future of Jean Memory
            </p>
            <div className="flex justify-center">
              <a
                href="https://discord.gg/NYru6Wbr"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full text-sm font-medium transition-all duration-200 hover:scale-105 shadow-lg hover:shadow-indigo-500/25"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419-.0189 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1568 2.4189Z"/>
                </svg>
                Join Discord
                <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
              </a>
            </div>
          </motion.div>

          {/* CTA Button */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ 
              type: "spring",
              stiffness: 260,
              damping: 20,
              delay: 0.9 
            }}
            className="mb-6"
          >
            <Link
              ref={buttonRef}
              href="/auth"
              className="group relative inline-flex items-center gap-2 sm:gap-3 px-6 sm:px-10 py-3 sm:py-5 text-base sm:text-xl font-bold rounded-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 transition-all duration-300 shadow-2xl hover:shadow-purple-500/25 hover:scale-105"
            >
              <span>One-Click Setup</span>
              <ArrowRight className="w-4 h-4 sm:w-6 sm:h-6 group-hover:translate-x-1 transition-transform" />
              
              {/* Button Glow Effect */}
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
            </Link>
          </motion.div>

          {/* Additional Info */}
          <motion.p
            className="text-xs sm:text-sm text-gray-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.1 }}
          >
            No credit card required • Free forever for personal use
          </motion.p>
        </motion.div>
      </div>

      {/* Animated Background Gradient */}
      <div className="absolute inset-0 opacity-30 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-conic from-purple-600 via-blue-600 to-purple-600 blur-3xl animate-spin-slow" />
      </div>
    </div>
  );
}
