"use client";

import { motion } from "framer-motion";
import { Brain, Database, Network, Sparkles } from "lucide-react";

const icons = [
  { Icon: Network, label: "Connect", color: "#ef4444", position: { x: -250, y: -150 } },
  { Icon: Sparkles, label: "AI Apps", color: "#06b6d4", position: { x: 250, y: -150 } },
  { Icon: Database, label: "Memory", color: "#f59e0b", position: { x: -350, y: 150 } },
  { Icon: Brain, label: "Claude", color: "#8b5cf6", position: { x: 350, y: 150 } },
];

export default function AnimatedIcons() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {icons.map((item, index) => {
        return (
          <motion.div
            key={item.label}
            className="absolute left-1/2 top-1/2"
            initial={{ opacity: 0, scale: 0, x: item.position.x, y: item.position.y }}
            animate={{
              opacity: [0, 0.5, 0.5, 0],
              scale: [0.8, 1, 1, 0.8],
            }}
            transition={{
              duration: 10,
              delay: index * 1.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="relative flex flex-col items-center gap-2">
              <div
                className="relative bg-black/50 backdrop-blur-sm p-4 rounded-full border"
                style={{ borderColor: item.color }}
              >
                <item.Icon size={32} style={{ color: item.color }} />
              </div>
              <p
                className="text-sm font-medium whitespace-nowrap"
                style={{ color: item.color }}
              >
                {item.label}
              </p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
} 