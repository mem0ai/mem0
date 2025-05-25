"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Text, Line, Sphere } from "@react-three/drei";
import * as THREE from "three";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { motion } from "framer-motion";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";

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
              {node.memory?.memory?.substring(0, 50) || "No content"}...
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
  const [selectedApp, setSelectedApp] = useState<string>("all");
  const [memoryLimit, setMemoryLimit] = useState<number>(50);
  const [apps, setApps] = useState<string[]>([]);

  useEffect(() => {
    // Fetch more memories initially (up to 100)
    fetchMemories(undefined, 1, 100);
  }, []);

  useEffect(() => {
    // Extract unique apps from memories
    const uniqueApps = [...new Set(memories.map(m => m.app_name).filter(Boolean))];
    setApps(uniqueApps);
  }, [memories]);

  useEffect(() => {
    // Filter memories by selected app
    const filteredMemories = selectedApp === "all" 
      ? memories 
      : memories.filter(m => m.app_name === selectedApp);

    // Limit the number of memories displayed
    const limitedMemories = filteredMemories.slice(0, memoryLimit);

    // Convert memories to graph nodes
    const graphNodes: GraphNode[] = limitedMemories.map((memory, index) => {
      const angle = (index / limitedMemories.length) * Math.PI * 2;
      const radius = 5 + (index % 3) * 2;
      const height = (Math.random() - 0.5) * 4;
      
      // Assign colors based on app
      const appColors: { [key: string]: string } = {
        "claude": "#8b5cf6",
        "twitter": "#3b82f6",
        "openmemory": "#10b981",
        "cursor": "#f59e0b",
        "windsurf": "#ef4444",
        "chatgpt": "#06b6d4"
      };
      const color = appColors[memory.app_name?.toLowerCase()] || "#6b7280";
      
      // Create meaningful connections based on:
      // 1. Same categories
      // 2. Close timestamps (within 24 hours)
      // 3. Same app
      const connections: string[] = [];
      
      limitedMemories.forEach((otherMemory, otherIndex) => {
        if (index === otherIndex) return;
        
        let connectionScore = 0;
        
        // Check for shared categories
        const sharedCategories = memory.categories?.filter((cat: any) => 
          otherMemory.categories?.includes(cat)
        ).length || 0;
        connectionScore += sharedCategories * 2;
        
        // Check for same app
        if (memory.app_name === otherMemory.app_name) {
          connectionScore += 1;
        }
        
        // Check for temporal proximity (within 24 hours)
        const timeDiff = Math.abs(memory.created_at - otherMemory.created_at);
        if (timeDiff < 24 * 60 * 60 * 1000) { // 24 hours in milliseconds
          connectionScore += 2;
        }
        
        // Create connection if score is high enough
        if (connectionScore >= 3 && connections.length < 5) {
          connections.push(otherMemory.id);
        }
      });
      
      return {
        id: memory.id,
        position: new THREE.Vector3(
          Math.cos(angle) * radius,
          height,
          Math.sin(angle) * radius
        ),
        memory,
        connections,
        color
      };
    });
    
    setNodes(graphNodes);
  }, [memories, selectedApp, memoryLimit]);

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
          <p className="text-sm text-zinc-400 mb-4">
            {nodes.length} memories visualized • Click to explore
          </p>
          
          {/* App Filter */}
          <div className="space-y-3">
            <Select value={selectedApp} onValueChange={setSelectedApp}>
              <SelectTrigger className="w-48 bg-zinc-800 border-zinc-700">
                <SelectValue placeholder="Filter by app" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Apps</SelectItem>
                {apps.map(app => (
                  <SelectItem key={app} value={app}>{app}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Memory Limit Slider */}
            <div className="space-y-2">
              <label className="text-xs text-zinc-400">
                Memory Limit: {memoryLimit}
              </label>
              <Slider
                value={[memoryLimit]}
                onValueChange={(value) => setMemoryLimit(value[0])}
                min={10}
                max={100}
                step={10}
                className="w-48"
              />
            </div>
          </div>
        </motion.div>
      </div>

      <Canvas 
        camera={{ position: [0, 5, 15], fov: 60 }}
        gl={{ 
          antialias: false, 
          alpha: false,
          powerPreference: "high-performance",
          preserveDrawingBuffer: false
        }}
        dpr={[1, 2]}
        performance={{ min: 0.5 }}
      >
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
          <p className="text-sm text-zinc-300 line-clamp-3">{selectedNode.memory?.memory || "No content available"}</p>
          <div className="flex gap-2 mt-3">
            <span className="text-xs text-zinc-500">
              {selectedNode.memory?.created_at ? new Date(selectedNode.memory.created_at).toLocaleDateString() : "Unknown date"}
            </span>
            {selectedNode.memory?.app_name && (
              <span className="text-xs text-zinc-500">• {selectedNode.memory.app_name}</span>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
} 