"use client";

import { useCallback, useEffect, useState } from "react";
import Particles, { initParticlesEngine } from "@tsparticles/react";
import { loadFull } from "tsparticles";

interface ParticleNetworkProps {
  id: string;
  className?: string;
  interactive?: boolean;
  particleCount?: number;
}

export default function ParticleNetwork({ 
  id,
  className, 
  interactive = true, 
  particleCount = 200 
}: ParticleNetworkProps) {
  const [init, setInit] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadFull(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  const particlesLoaded = useCallback(async (container: any) => {
    // Optional callback
  }, []);

  // Desktop: Full interactive experience
  // Mobile: Simplified but visible
  const options = {
    fullScreen: {
      enable: false,
      zIndex: 0,
    },
    background: {
      color: {
        value: "transparent",
      },
    },
    fpsLimit: 120,
    interactivity: {
      events: {
        onClick: {
          enable: interactive && !isMobile, // Desktop only: click to add particles
          mode: "push",
        },
        onHover: {
          enable: interactive && !isMobile, // Desktop only: hover connections
          mode: "grab",
        },
      },
      modes: {
        push: {
          quantity: 2,
        },
        grab: {
          distance: 200,
          links: {
            opacity: 0.5,
          },
        },
      },
    },
    particles: {
      color: {
        value: isMobile 
          ? "#9ca3af"  // Bright and visible on mobile
          : ["#9ca3af", "#6b7280", "#4b5563"], // Original varied colors on desktop
      },
              links: {
          color: "#6b7280",
          distance: 150,
          enable: true,
          opacity: isMobile ? 0.7 : 0.4, // Even higher opacity on mobile for visibility
          width: 1,
        },
      move: {
        direction: "none",
        enable: true,
        outModes: {
          default: "bounce",
        },
        random: true,
        speed: isMobile ? 0.8 : 1, // Slightly slower on mobile for battery
        straight: false,
      },
      number: {
        value: isMobile ? 50 : particleCount, // Fewer particles on mobile
      },
              opacity: {
          value: isMobile ? 0.9 : 0.6, // Even higher opacity on mobile
        },
      shape: {
        type: "circle",
      },
      size: {
        value: { min: 1, max: isMobile ? 3 : 3 }, // Consistent size
      },
    },
    detectRetina: true,
  };

  if (!init) {
    return null;
  }

  return (
    <Particles
      id={id}
      className={className}
      particlesLoaded={particlesLoaded}
      options={options as any}
    />
  );
} 