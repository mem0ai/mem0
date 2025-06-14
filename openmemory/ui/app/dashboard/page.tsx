"use client";

import { Install } from "@/components/dashboard/Install";
import Stats from "@/components/dashboard/Stats";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import { usePostHog } from 'posthog-js/react';
import { useEffect } from 'react';
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { AnalysisPanel } from "@/components/dashboard/AnalysisPanel";

export default function DashboardPage() {
  const { user } = useAuth();
  const posthog = usePostHog();

  // 📊 Track dashboard visits
  useEffect(() => {
    if (posthog && user) {
      posthog.capture('dashboard_visited', {
        user_id: user.id,
        user_email: user.email
      });
    }
  }, [posthog, user]);

  return (
    <div className="min-h-screen bg-black relative">
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="dashboard-particles" className="h-full w-full" interactive={false} particleCount={80} />
      </div>
      <div className="container mx-auto px-4 py-8 max-w-7xl relative z-10">
        {/* Welcome Section */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-white mb-2">
            Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}
          </h1>
          <p className="text-zinc-400">
            Set up your AI tools and start building your memory bank
          </p>
        </motion.div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Left Column: Installation */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="lg:col-span-1"
          >
            <Install />
          </motion.div>

          {/* Right Column: Analysis and Stats */}
          <div className="flex flex-col gap-6">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <AnalysisPanel />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              <Stats />
            </motion.div>
          </div>
        </div>

        {/* Memories Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="space-y-6"
        >
          <div className="border-t border-zinc-800 pt-6">
            <h2 className="text-2xl font-semibold text-white mb-6">Your Memories</h2>
            <MemoryFilters />
          </div>
          <MemoriesSection />
        </motion.div>
      </div>
    </div>
  );
}
