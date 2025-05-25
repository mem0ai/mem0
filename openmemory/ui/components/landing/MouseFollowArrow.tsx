"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

interface MouseFollowArrowProps {
  targetRef: React.RefObject<HTMLElement | HTMLAnchorElement | null>;
}

export default function MouseFollowArrow({ targetRef }: MouseFollowArrowProps) {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [targetPosition, setTargetPosition] = useState({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const updateMousePosition = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
      setIsVisible(true);
    };

    const updateTargetPosition = () => {
      if (targetRef.current) {
        const rect = targetRef.current.getBoundingClientRect();
        setTargetPosition({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        });
      }
    };

    window.addEventListener("mousemove", updateMousePosition);
    window.addEventListener("resize", updateTargetPosition);
    updateTargetPosition();

    return () => {
      window.removeEventListener("mousemove", updateMousePosition);
      window.removeEventListener("resize", updateTargetPosition);
    };
  }, [targetRef]);

  // Calculate distance
  const distance = Math.sqrt(
    Math.pow(targetPosition.x - mousePosition.x, 2) +
    Math.pow(targetPosition.y - mousePosition.y, 2)
  );

  // Don't show arrow if too close to button
  if (distance < 100 || !isVisible) return null;

  // Calculate the line path
  const lineLength = distance - 50; // Stop 50px before the button
  const angle = Math.atan2(
    targetPosition.y - mousePosition.y,
    targetPosition.x - mousePosition.x
  );
  
  // Calculate end point of the line (closer to button)
  const endX = mousePosition.x + Math.cos(angle) * lineLength;
  const endY = mousePosition.y + Math.sin(angle) * lineLength;

  return (
    <motion.svg
      className="fixed pointer-events-none z-40 inset-0 w-full h-full"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <defs>
        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.2" />
          <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="1" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      {/* Main line */}
      <motion.line
        x1={mousePosition.x}
        y1={mousePosition.y}
        x2={endX}
        y2={endY}
        stroke="url(#lineGradient)"
        strokeWidth="2"
        filter="url(#glow)"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.3 }}
      />
      
      {/* Arrow head at the end */}
      <motion.path
        d={`M ${endX - 15 * Math.cos(angle - 0.5)} ${endY - 15 * Math.sin(angle - 0.5)} 
            L ${endX} ${endY} 
            L ${endX - 15 * Math.cos(angle + 0.5)} ${endY - 15 * Math.sin(angle + 0.5)}`}
        stroke="url(#lineGradient)"
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter="url(#glow)"
      />
      
      {/* Pulsing circle at mouse position */}
      <motion.circle
        cx={mousePosition.x}
        cy={mousePosition.y}
        r="5"
        fill="#8b5cf6"
        filter="url(#glow)"
        animate={{
          r: [5, 8, 5],
          opacity: [0.8, 0.4, 0.8],
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      
      {/* Animated dots along the line */}
      {[0.3, 0.5, 0.7].map((offset, i) => (
        <motion.circle
          key={i}
          cx={mousePosition.x + (endX - mousePosition.x) * offset}
          cy={mousePosition.y + (endY - mousePosition.y) * offset}
          r="2"
          fill="#3b82f6"
          initial={{ opacity: 0 }}
          animate={{ 
            opacity: [0, 1, 0],
            r: [1, 3, 1]
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: i * 0.3,
            ease: "easeInOut",
          }}
        />
      ))}
    </motion.svg>
  );
} 