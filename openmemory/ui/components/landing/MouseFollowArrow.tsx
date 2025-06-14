"use client";

import { useEffect, useRef, useState, useLayoutEffect } from "react";
import { motion } from "framer-motion";

interface MouseFollowArrowProps {
  targetRef: React.RefObject<HTMLElement | HTMLAnchorElement | null>;
}

export default function MouseFollowArrow({ targetRef }: MouseFollowArrowProps) {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [targetPosition, setTargetPosition] = useState({ x: 0, y: 0 });
  const [isVisible, setIsVisible] = useState(false);

  useLayoutEffect(() => {
    const updateTargetPosition = () => {
      if (targetRef.current) {
        const rect = targetRef.current.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            setTargetPosition({
              x: rect.left + rect.width / 2,
              y: rect.top + rect.height / 2,
            });
        }
      }
    };

    const updateMousePosition = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
      setIsVisible(true);
    };

    window.addEventListener("mousemove", updateMousePosition);
    window.addEventListener("resize", updateTargetPosition);
    
    const intervalId = setInterval(updateTargetPosition, 100);

    return () => {
      window.removeEventListener("mousemove", updateMousePosition);
      window.removeEventListener("resize", updateTargetPosition);
      clearInterval(intervalId);
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
      {/* Main line */}
      <motion.line
        x1={mousePosition.x}
        y1={mousePosition.y}
        x2={endX}
        y2={endY}
        stroke="gray"
        strokeWidth="1"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.3 }}
      />
      
      {/* Arrow head at the end */}
      <motion.path
        d={`M ${endX - 10 * Math.cos(angle - 0.4)} ${endY - 10 * Math.sin(angle - 0.4)} 
            L ${endX} ${endY} 
            L ${endX - 10 * Math.cos(angle + 0.4)} ${endY - 10 * Math.sin(angle + 0.4)}`}
        stroke="gray"
        strokeWidth="1"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </motion.svg>
  );
} 