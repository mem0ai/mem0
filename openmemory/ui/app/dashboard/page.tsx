"use client";

import { Install } from "@/components/dashboard/Install";
import Stats from "@/components/dashboard/Stats";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-black">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Installation Section - Takes up 2 columns on large screens */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="lg:col-span-2"
          >
            <Install />
          </motion.div>

          {/* Stats Section - Takes up 1 column */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Stats />
          </motion.div>
        </div>

        {/* Memories Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
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
