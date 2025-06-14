"use client";

import { useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Shield, Zap, Globe, Key, Github, Star } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Image from "next/image";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
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
        <ParticleNetwork id="landing-particles" />
      </div>

      {/* Mouse Follow Arrow */}
      <MouseFollowArrow targetRef={buttonRef} />

      {/* Gradient Overlays */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-950/60 via-transparent to-slate-950/60" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/80 to-black" />

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
            className="text-6xl sm:text-7xl md:text-8xl font-semibold mb-6 text-gray-200 tracking-tight"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            Jean
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="text-lg sm:text-xl text-gray-400 mb-10 max-w-xl mx-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            Your secure memory across AI applications
          </motion.p>

          <div className="my-12 sm:my-16 flex flex-col items-center justify-center gap-6">
            {/* CTA Button */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{
                type: "spring",
                stiffness: 260,
                damping: 20,
                delay: 0.7
              }}
            >
              <Link
                ref={buttonRef}
                href="/auth"
                className="group relative inline-flex items-center justify-center gap-3 px-12 py-4 text-xl font-bold rounded-md bg-black text-white border border-gray-600 hover:bg-gray-800 transition-all duration-300 shadow-lg hover:shadow-xl hover:shadow-slate-500/10 hover:scale-105"
              >
                <Key className="w-5 h-5 group-hover:-rotate-12 transition-transform" />
                <span>Sign in with Jean</span>
              </Link>
            </motion.div>

            {/* GitHub Badge */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.8 }}
            >
              <a
                href="https://github.com/jonathan-politzki/your-memory"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-3 text-sm text-gray-400 hover:text-white transition-colors"
              >
                <span className="font-medium">Trusted by Open Source</span>
                <div className="w-px h-4 bg-gray-600" />
                <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 text-yellow-400" />
                    <span className="font-medium text-white">59</span>
                </div>
              </a>
            </motion.div>
          </div>

          {/* Features */}
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-3 gap-8 my-16 sm:my-20"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.9 }}
          >
            <div className="flex flex-col items-center text-center p-4">
              <Shield className="w-8 h-8 text-blue-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Secure & Private</h3>
              <p className="text-sm text-gray-400 max-w-xs">You own your data—forever.</p>
            </div>
            <div className="flex flex-col items-center text-center p-4">
              <Zap className="w-8 h-8 text-blue-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Lightning Fast</h3>
              <p className="text-sm text-gray-400 max-w-xs">Instant access to your context across all AI tools.</p>
            </div>
            <div className="flex flex-col items-center text-center p-4">
              <Globe className="w-8 h-8 text-blue-400 mb-4" />
              <h3 className="text-lg font-semibold mb-2">Universal</h3>
              <p className="text-sm text-gray-400 max-w-xs">Claude, Cursor, ChatGPT (soon), etc.</p>
            </div>
          </motion.div>

          {/* Additional Info */}
          <motion.p
            className="text-xs sm:text-sm text-gray-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.1 }}
          >
            No credit card required • Free forever for personal use • <a href="/privacy-policy" className="underline hover:text-white">Privacy Policy</a>
          </motion.p>
        </motion.div>
      </div>
    </div>
  );
}
