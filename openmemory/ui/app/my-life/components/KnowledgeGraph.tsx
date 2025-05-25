"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Text, Line, Sphere } from "@react-three/drei";
import * as THREE from "three";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { motion } from "framer-motion";

interface GraphNode {
  id: string;
  position: THREE.Vector3;
  memory: any;
  connections: string[];
  color: string;
}

interface KnowledgeGraphProps {
  onMemorySelect: (memoryId: string | null) => void;
}

function GraphNodes({ nodes, onNodeClick }: { nodes: GraphNode[], onNodeClick: (node: GraphNode) => void }) {
  const [hovered, setHovered] = useState<string | null>(null);
  
  return (
    <>
      {nodes.map((node) => (
        <group key={node.id} position={node.position}>
          <Sphere
            args={[0.3, 32, 32]}
            onClick={() => onNodeClick(node)}
            onPointerOver={() => setHovered(node.id)}
            onPointerOut={() => setHovered(null)}
          >
            <meshPhysicalMaterial
              color={node.color}
              emissive={node.color}
              emissiveIntensity={hovered === node.id ? 0.5 : 0.2}
              roughness={0.2}
              metalness={0.8}
              clearcoat={1}
              clearcoatRoughness={0}
            />
          </Sphere>
          {hovered === node.id && (
            <Text
              position={[0, 0.6, 0]}
              fontSize={0.15}
              color="white"
              anchorX="center"
              anchorY="middle"
            >
              {node.memory.content.substring(0, 50)}...
            </Text>
          )}
        </group>
      ))}
    </>
  );
}

function GraphConnections({ nodes }: { nodes: GraphNode[] }) {
  const lines = useMemo(() => {
    const connections: { start: THREE.Vector3; end: THREE.Vector3 }[] = [];
    
    nodes.forEach((node) => {
      node.connections.forEach((targetId) => {
        const targetNode = nodes.find(n => n.id === targetId);
        if (targetNode) {
          connections.push({
            start: node.position,
            end: targetNode.position
          });
        }
      });
    });
    
    return connections;
  }, [nodes]);

  return (
    <>
      {lines.map((line, index) => (
        <Line
          key={index}
          points={[line.start, line.end]}
          color="#4a5568"
          lineWidth={1}
          opacity={0.3}
        />
      ))}
    </>
  );
}

function AnimatedParticles() {
  const particlesRef = useRef<THREE.Points>(null);
  const particleCount = 100;
  
  const positions = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      pos[i] = (Math.random() - 0.5) * 20;
      pos[i + 1] = (Math.random() - 0.5) * 20;
      pos[i + 2] = (Math.random() - 0.5) * 20;
    }
    return pos;
  }, []);

  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = state.clock.elapsedTime * 0.05;
      particlesRef.current.rotation.x = state.clock.elapsedTime * 0.03;
    }
  });

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        color="#8b5cf6"
        transparent
        opacity={0.6}
        sizeAttenuation
      />
    </points>
  );
}

export default function KnowledgeGraph({ onMemorySelect }: KnowledgeGraphProps) {
  const { memories, fetchMemories } = useMemoriesApi();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    fetchMemories();
  }, []);

  useEffect(() => {
    // Convert memories to graph nodes
    const graphNodes: GraphNode[] = memories.slice(0, 50).map((memory, index) => {
      const angle = (index / Math.min(memories.length, 50)) * Math.PI * 2;
      const radius = 5 + (index % 3) * 2;
      const height = (Math.random() - 0.5) * 4;
      
      // Assign colors based on categories or apps
      const colors = ["#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4"];
      const color = colors[index % colors.length];
      
      return {
        id: memory.id,
        position: new THREE.Vector3(
          Math.cos(angle) * radius,
          height,
          Math.sin(angle) * radius
        ),
        memory,
        connections: memories
          .slice(0, 50)
          .filter((m, i) => i !== index && Math.random() > 0.7)
          .slice(0, 3)
          .map(m => m.id),
        color
      };
    });
    
    setNodes(graphNodes);
  }, [memories]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    onMemorySelect(node.id);
  };

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-4 left-4 z-10">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-zinc-900/80 backdrop-blur-sm rounded-lg p-4 border border-zinc-800"
        >
          <h2 className="text-xl font-semibold text-white mb-2">Knowledge Graph</h2>
          <p className="text-sm text-zinc-400">
            {nodes.length} memories visualized • Click to explore
          </p>
        </motion.div>
      </div>

      <Canvas camera={{ position: [0, 5, 15], fov: 60 }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#8b5cf6" />
        
        <AnimatedParticles />
        <GraphNodes nodes={nodes} onNodeClick={handleNodeClick} />
        <GraphConnections nodes={nodes} />
        
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          autoRotate={true}
          autoRotateSpeed={0.5}
        />
        
        <fog attach="fog" args={["#0a0a0a", 10, 30]} />
      </Canvas>

      {selectedNode && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="absolute bottom-4 left-4 right-4 bg-zinc-900/90 backdrop-blur-sm rounded-lg p-4 border border-zinc-800"
        >
          <h3 className="text-lg font-semibold text-white mb-2">Selected Memory</h3>
          <p className="text-sm text-zinc-300 line-clamp-3">{selectedNode.memory.content}</p>
          <div className="flex gap-2 mt-3">
            <span className="text-xs text-zinc-500">
              {new Date(selectedNode.memory.created_at).toLocaleDateString()}
            </span>
            {selectedNode.memory.app_name && (
              <span className="text-xs text-zinc-500">• {selectedNode.memory.app_name}</span>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
} 