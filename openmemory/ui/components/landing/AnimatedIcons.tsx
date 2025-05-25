"use client";

import { motion } from "framer-motion";
import { Brain, Bot, Cpu, Database, Network, Sparkles } from "lucide-react";

const icons = [
  { Icon: Brain, label: "Claude", color: "#8b5cf6", delay: 0 },
  { Icon: Bot, label: "OpenAI", color: "#10b981", delay: 0.2 },
  { Icon: Cpu, label: "Gemini", color: "#3b82f6", delay: 0.4 },
  { Icon: Database, label: "Memory", color: "#f59e0b", delay: 0.6 },
  { Icon: Network, label: "Connect", color: "#ef4444", delay: 0.8 },
  { Icon: Sparkles, label: "AI Apps", color: "#06b6d4", delay: 1 },
];

export default function AnimatedIcons() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {icons.map((item, index) => {
        const angle = (index / icons.length) * 2 * Math.PI;
        const radius = 300;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;

        return (
          <motion.div
            key={item.label}
            className="absolute left-1/2 top-1/2"
            initial={{ opacity: 0, scale: 0 }}
            animate={{
              opacity: [0, 1, 1, 0],
              scale: [0, 1, 1, 0],
              x: [0, x, x * 1.2, x * 1.5],
              y: [0, y, y * 1.2, y * 1.5],
            }}
            transition={{
              duration: 8,
              delay: item.delay,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="relative">
              <motion.div
                className="absolute inset-0 rounded-full blur-xl"
                style={{ backgroundColor: item.color }}
                animate={{
                  scale: [1, 1.5, 1],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
              <div
                className="relative bg-black/50 backdrop-blur-sm p-4 rounded-full border"
                style={{ borderColor: item.color }}
              >
                <item.Icon size={32} style={{ color: item.color }} />
              </div>
              <motion.p
                className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-sm font-medium whitespace-nowrap"
                style={{ color: item.color }}
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 1, 1, 0] }}
                transition={{
                  duration: 8,
                  delay: item.delay + 0.5,
                  repeat: Infinity,
                }}
              >
                {item.label}
              </motion.p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
} 