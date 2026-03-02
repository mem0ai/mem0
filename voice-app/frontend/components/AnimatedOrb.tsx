'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

interface OrbProps {
  userSpeaking: boolean;
  aiSpeaking: boolean;
}

function Orb({ userSpeaking, aiSpeaking }: OrbProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const particlesRef = useRef<THREE.Points>(null);

  // Create particle geometry
  const particles = useMemo(() => {
    const count = 1000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const sizes = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      const i3 = i * 3;

      // Random position in a sphere
      const radius = 2 + Math.random() * 3;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;

      positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i3 + 2] = radius * Math.cos(phi);

      // Color (will be modified based on speaking state)
      colors[i3] = 1;
      colors[i3 + 1] = 1;
      colors[i3 + 2] = 1;

      sizes[i] = Math.random() * 0.1 + 0.05;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    return geometry;
  }, []);

  useFrame((state) => {
    const time = state.clock.getElapsedTime();

    // Rotate orb
    if (meshRef.current) {
      meshRef.current.rotation.y = time * 0.2;
      meshRef.current.rotation.x = Math.sin(time * 0.3) * 0.1;
    }

    // Animate particles
    if (particlesRef.current) {
      const positions = particlesRef.current.geometry.attributes.position.array as Float32Array;
      const colors = particlesRef.current.geometry.attributes.color.array as Float32Array;

      for (let i = 0; i < positions.length; i += 3) {
        // Particle movement
        const noise = Math.sin(time + i) * 0.01;
        positions[i + 1] += noise;

        // Reset if particle goes too high
        if (positions[i + 1] > 5) {
          positions[i + 1] = -2;
        }

        // Color based on speaking state
        if (userSpeaking) {
          // Blue smoke #4A90E2
          colors[i] = 0.29;
          colors[i + 1] = 0.56;
          colors[i + 2] = 0.89;
        } else if (aiSpeaking) {
          // Pink smoke #E24A90
          colors[i] = 0.89;
          colors[i + 1] = 0.29;
          colors[i + 2] = 0.56;
        } else {
          // Neutral/white
          colors[i] = 0.8;
          colors[i + 1] = 0.8;
          colors[i + 2] = 0.8;
        }
      }

      particlesRef.current.geometry.attributes.position.needsUpdate = true;
      particlesRef.current.geometry.attributes.color.needsUpdate = true;
    }
  });

  return (
    <>
      {/* Main orb */}
      <Sphere ref={meshRef} args={[1.5, 64, 64]}>
        <meshStandardMaterial
          color={userSpeaking ? '#4A90E2' : aiSpeaking ? '#E24A90' : '#6B7280'}
          metalness={0.8}
          roughness={0.2}
          emissive={userSpeaking ? '#4A90E2' : aiSpeaking ? '#E24A90' : '#374151'}
          emissiveIntensity={0.5}
        />
      </Sphere>

      {/* Particle system */}
      <points ref={particlesRef} geometry={particles}>
        <pointsMaterial
          size={0.1}
          vertexColors
          transparent
          opacity={0.6}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1} />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#4A90E2" />
    </>
  );
}

export function AnimatedOrb({ userSpeaking, aiSpeaking }: OrbProps) {
  return (
    <div className="w-full h-full">
      <Canvas camera={{ position: [0, 0, 8], fov: 50 }}>
        <Orb userSpeaking={userSpeaking} aiSpeaking={aiSpeaking} />
        <OrbitControls enableZoom={false} enablePan={false} />
      </Canvas>
    </div>
  );
}
