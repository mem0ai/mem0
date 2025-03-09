"use client";

import darkLogo from "@/images/dark.svg";
import lightLogo from "@/images/light.svg";
import React from "react";
import Image from "next/image";

export default function ThemeAwareLogo({
  width = 120,
  height = 40,
  variant = "default",
  isDarkMode = false,
}: {
  width?: number;
  height?: number;
  variant?: "default" | "collapsed";
  isDarkMode?: boolean;
}) {
  // For collapsed variant, always use the icon
  if (variant === "collapsed") {
    return (
      <div 
        className={`flex items-center justify-center rounded-full ${isDarkMode ? 'bg-[#6366f1]' : 'bg-[#4f46e5]'}`}
        style={{ width, height }}
      >
        <span className="text-white font-bold text-lg">M</span>
      </div>
    );
  }
  
  // For default variant, use the full logo image
  const logoSrc = isDarkMode ? darkLogo : lightLogo;
  
  return (
    <Image
      src={logoSrc}
      alt="Mem0.ai"
      width={width}
      height={height}
    />
  );
}