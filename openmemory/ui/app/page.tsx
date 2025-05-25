"use client";

import { useRef } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Shield, Zap, Globe } from "lucide-react";
import Link from "next/link";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import AnimatedSphere from "@/components/landing/AnimatedSphere";
import AnimatedIcons from "@/components/landing/AnimatedIcons";
import MouseFollowArrow from "@/components/landing/MouseFollowArrow";

export default function LandingPage() {
  const buttonRef = useRef<HTMLAnchorElement>(null);

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
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-4xl mx-auto"
        >
          {/* Logo/Title */}
          <motion.h1
            className="text-6xl md:text-8xl font-bold mb-6 bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            Jean Memory
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="text-xl md:text-2xl text-gray-300 mb-12 max-w-2xl mx-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            Your secure, unified memory layer across all AI applications
          </motion.p>

          {/* Features */}
          <motion.div
            className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <Shield className="w-8 h-8 text-purple-400 mb-3 mx-auto" />
              <h3 className="text-lg font-semibold mb-2">Secure & Private</h3>
              <p className="text-sm text-gray-400">Your memories stay yours with end-to-end encryption</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <Zap className="w-8 h-8 text-blue-400 mb-3 mx-auto" />
              <h3 className="text-lg font-semibold mb-2">Lightning Fast</h3>
              <p className="text-sm text-gray-400">Instant access to your context across all AI tools</p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-6 border border-white/10">
              <Globe className="w-8 h-8 text-cyan-400 mb-3 mx-auto" />
              <h3 className="text-lg font-semibold mb-2">Universal</h3>
              <p className="text-sm text-gray-400">Works with Claude, GPT, Gemini, and more</p>
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
              delay: 0.8 
            }}
          >
            <Link
              ref={buttonRef}
              href="/dashboard"
              className="group relative inline-flex items-center gap-3 px-10 py-5 text-xl font-bold rounded-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 transition-all duration-300 shadow-2xl hover:shadow-purple-500/25 hover:scale-105"
            >
              <span>One-Click Setup</span>
              <ArrowRight className="w-6 h-6 group-hover:translate-x-1 transition-transform" />
              
              {/* Button Glow Effect */}
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
            </Link>
          </motion.div>

          {/* Additional Info */}
          <motion.p
            className="mt-8 text-sm text-gray-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1 }}
          >
            No credit card required • Free forever for personal use
          </motion.p>
        </motion.div>
      </div>

      {/* Animated Background Gradient */}
      <div className="absolute inset-0 opacity-30">
        <div className="absolute inset-0 bg-gradient-conic from-purple-600 via-blue-600 to-purple-600 blur-3xl animate-spin-slow" />
      </div>
    </div>
  );
}
