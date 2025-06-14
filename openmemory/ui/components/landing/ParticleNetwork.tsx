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

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadFull(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  const particlesLoaded = useCallback(async (container: any) => {
    // Optional: Add any logic when particles are loaded
  }, []);

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
          enable: interactive,
          mode: "push",
        },
        onHover: {
          enable: interactive,
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
        value: ["#9ca3af", "#6b7280", "#4b5563"],
      },
      links: {
        color: "#6b7280",
        distance: 150,
        enable: true,
        opacity: 0.4,
        width: 1,
      },
      move: {
        direction: "none",
        enable: true,
        outModes: {
          default: "bounce",
        },
        random: true,
        speed: 1,
        straight: false,
      },
      number: {
        value: particleCount,
      },
      opacity: {
        value: 0.6,
      },
      shape: {
        type: "circle",
      },
      size: {
        value: { min: 1, max: 3 },
      },
    },
    detectRetina: true,
  }

  return (
    <>
      {init && (
        <Particles
          id={id}
          className={className}
          particlesLoaded={particlesLoaded}
          options={options as any}
        />
      )}
    </>
  );
} 