"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Sphere, Html } from "@react-three/drei";
import * as THREE from "three";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { motion, AnimatePresence } from "framer-motion";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { RefreshCw, Info, Settings, X } from "lucide-react";
import { constants } from "@/components/shared/source-app";

interface GraphNode {
  id: string;
  position: THREE.Vector3;
  targetPosition: THREE.Vector3;
  memory: any;
  color: string;
  size: number;
}

interface KnowledgeGraphProps {
  onMemorySelect: (memoryId: string | null) => void;
}

// Simulate t-SNE/PCA-like clustering based on categories and metadata
function calculateClusterPositions(memories: any[], clusterStrength: number = 1) {
  const positions: THREE.Vector3[] = [];
  const categoryGroups: { [key: string]: number[] } = {};
  const appGroups: { [key: string]: number[] } = {};
  
  // Group memories by primary category and app
  memories.forEach((memory, index) => {
    const primaryCategory = memory.categories?.[0] || 'uncategorized';
    const app = memory.app_name || 'unknown';
    
    if (!categoryGroups[primaryCategory]) categoryGroups[primaryCategory] = [];
    if (!appGroups[app]) appGroups[app] = [];
    
    categoryGroups[primaryCategory].push(index);
    appGroups[app].push(index);
  });
  
  // Calculate base positions for each category cluster
  const categoryCount = Object.keys(categoryGroups).length;
  const categoryPositions: { [key: string]: THREE.Vector3 } = {};
  
  Object.keys(categoryGroups).forEach((category, i) => {
    const angle = (i / categoryCount) * Math.PI * 2;
    const radius = 8;
    categoryPositions[category] = new THREE.Vector3(
      Math.cos(angle) * radius,
      (Math.random() - 0.5) * 4,
      Math.sin(angle) * radius
    );
  });
  
  // Position each memory near its category cluster with some variance
  memories.forEach((memory, index) => {
    const primaryCategory = memory.categories?.[0] || 'uncategorized';
    const basePos = categoryPositions[primaryCategory] || new THREE.Vector3(0, 0, 0);
    
    // Add variance based on secondary factors
    const variance = 3;
    const timeOffset = (memory.created_at % 1000000) / 1000000 - 0.5; // Normalize time to -0.5 to 0.5
    
    // Create position with controlled randomness
    const position = new THREE.Vector3(
      basePos.x + (Math.random() - 0.5) * variance * clusterStrength,
      basePos.y + timeOffset * 2, // Time affects Y position slightly
      basePos.z + (Math.random() - 0.5) * variance * clusterStrength
    );
    
    // Pull memories from same app slightly closer together
    const sameAppMemories = appGroups[memory.app_name || 'unknown'];
    if (sameAppMemories.length > 1) {
      const appCenter = new THREE.Vector3();
      sameAppMemories.forEach(idx => {
        if (positions[idx]) {
          appCenter.add(positions[idx]);
        }
      });
      appCenter.divideScalar(sameAppMemories.length);
      
      // Move slightly toward app center
      position.lerp(appCenter, 0.2);
    }
    
    positions[index] = position;
  });
  
  return positions;
}

function GraphNodes({ nodes, onNodeClick }: { nodes: GraphNode[], onNodeClick: (node: GraphNode) => void }) {
  const [hovered, setHovered] = useState<string | null>(null);
  
  // Smooth position transitions
  useFrame((state, delta) => {
    nodes.forEach(node => {
      node.position.lerp(node.targetPosition, 0.1);
    });
  });
  
  return (
    <>
      {nodes.map((node) => (
        <group key={node.id} position={node.position}>
          <Sphere
            args={[node.size, 32, 32]}
            onClick={() => onNodeClick(node)}
            onPointerOver={() => setHovered(node.id)}
            onPointerOut={() => setHovered(null)}
          >
            <meshPhysicalMaterial
              color={node.color}
              emissive={node.color}
              emissiveIntensity={hovered === node.id ? 0.8 : 0.3}
              roughness={0.2}
              metalness={0.8}
              clearcoat={1}
              clearcoatRoughness={0}
              transparent
              opacity={hovered === node.id ? 1 : 0.8}
            />
          </Sphere>
          {hovered === node.id && (
            <Html distanceFactor={10}>
              <div className="bg-zinc-900/95 text-white p-3 rounded-lg text-xs max-w-xs shadow-xl border border-zinc-700">
                <p className="font-semibold mb-1 text-sm">{node.memory?.app_name || "Unknown"}</p>
                <p className="line-clamp-3 mb-2">{node.memory?.memory || "No content"}</p>
                <div className="flex flex-wrap gap-1 text-zinc-400">
                  <span>{node.memory?.created_at ? new Date(node.memory.created_at).toLocaleDateString() : ""}</span>
                  {node.memory?.categories?.length > 0 && (
                    <>
                      <span>•</span>
                      <span className="text-purple-400">{node.memory.categories.join(", ")}</span>
                    </>
                  )}
                </div>
              </div>
            </Html>
          )}
        </group>
      ))}
    </>
  );
}

function AnimatedParticles() {
  const particlesRef = useRef<THREE.Points>(null);
  const particleCount = 50;
  
  const positions = useMemo(() => {
    const pos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      pos[i] = (Math.random() - 0.5) * 30;
      pos[i + 1] = (Math.random() - 0.5) * 30;
      pos[i + 2] = (Math.random() - 0.5) * 30;
    }
    return pos;
  }, []);

  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = state.clock.elapsedTime * 0.02;
      particlesRef.current.rotation.x = state.clock.elapsedTime * 0.01;
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
        size={0.03}
        color="#8b5cf6"
        transparent
        opacity={0.3}
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
  const [memoryLimit, setMemoryLimit] = useState<number>(60);
  const [clusterStrength, setClusterStrength] = useState<number>(1);
  const [apps, setApps] = useState<string[]>([]);
  const [showControls, setShowControls] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Check if mobile
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    // Fetch more memories initially
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

    // Calculate positions using clustering algorithm
    const positions = calculateClusterPositions(limitedMemories, clusterStrength);

    // Convert memories to graph nodes
    const graphNodes: GraphNode[] = limitedMemories.map((memory, index) => {
      // Assign colors based on app
      const appColors: { [key: string]: string } = {
        "claude": "#8b5cf6",
        "twitter": "#3b82f6", 
        "jean memory": "#10b981",
        "cursor": "#f59e0b",
        "windsurf": "#ef4444",
        "chatgpt": "#06b6d4"
      };
      const color = appColors[memory.app_name?.toLowerCase()] || "#6b7280";
      
      // Size based on content length
      const size = Math.min(Math.max(memory.memory?.length / 500 || 0.3, 0.3), 0.8);
      
      return {
        id: memory.id,
        position: positions[index].clone(),
        targetPosition: positions[index],
        memory,
        color,
        size
      };
    });
    
    setNodes(graphNodes);
  }, [memories, selectedApp, memoryLimit, clusterStrength]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    onMemorySelect(node.id);
  };

  const handleRefresh = () => {
    fetchMemories(undefined, 1, 100);
  };

  return (
    <div className="relative w-full h-full bg-zinc-950 overflow-hidden">
      {/* Mobile Control Buttons */}
      {isMobile && (
        <div className="absolute top-2 left-2 right-2 z-20 flex justify-between">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowControls(!showControls)}
            className="h-8 w-8 bg-zinc-900/90 backdrop-blur-sm"
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowLegend(!showLegend)}
            className="h-8 w-8 bg-zinc-900/90 backdrop-blur-sm"
          >
            <Info className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Control Panel */}
      <AnimatePresence>
        {(!isMobile || showControls) && (
          <motion.div
            initial={{ opacity: 0, x: isMobile ? -100 : 0, y: isMobile ? 0 : -20 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: isMobile ? -100 : 0 }}
            className={`
              absolute z-10
              ${isMobile ? 'inset-0 bg-zinc-900/95' : 'top-4 left-4 bg-zinc-900/90'}
              backdrop-blur-sm rounded-lg border border-zinc-800
              ${isMobile ? 'p-6' : 'p-4'}
            `}
          >
            {isMobile && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowControls(false)}
                className="absolute top-2 right-2 h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
            
            <div className="space-y-4 max-w-sm">
              <div className="flex items-center justify-between">
                <h2 className={`${isMobile ? 'text-2xl' : 'text-xl'} font-semibold text-white`}>
                  Knowledge Graph
                </h2>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleRefresh}
                  className="h-8 w-8"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
              
              <p className="text-sm text-zinc-400">
                {nodes.length} memories visualized
              </p>
              
              {/* App Filter */}
              <div className="space-y-2">
                <label className="text-xs text-zinc-400">Filter by App</label>
                <Select value={selectedApp} onValueChange={setSelectedApp}>
                  <SelectTrigger className={`${isMobile ? 'w-full' : 'w-48'} bg-zinc-800 border-zinc-700`}>
                    <SelectValue placeholder="Filter by app" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Apps</SelectItem>
                    {apps.map(app => (
                      <SelectItem key={app} value={app}>
                        {constants[app as keyof typeof constants]?.name || app}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
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
                  className={isMobile ? 'w-full' : 'w-48'}
                />
              </div>
              
              {/* Cluster Strength Slider */}
              <div className="space-y-2">
                <label className="text-xs text-zinc-400">
                  Cluster Strength: {clusterStrength.toFixed(1)}
                </label>
                <Slider
                  value={[clusterStrength]}
                  onValueChange={(value) => setClusterStrength(value[0])}
                  min={0.5}
                  max={2}
                  step={0.1}
                  className={isMobile ? 'w-full' : 'w-48'}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Legend */}
      <AnimatePresence>
        {(!isMobile || showLegend) && (
          <motion.div
            initial={{ opacity: 0, x: isMobile ? 100 : 0, y: isMobile ? 0 : -20 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: isMobile ? 100 : 0 }}
            transition={{ delay: isMobile ? 0 : 0.2 }}
            className={`
              absolute z-10
              ${isMobile ? 'inset-0 bg-zinc-900/95' : 'top-4 right-4 bg-zinc-900/90'}
              backdrop-blur-sm rounded-lg border border-zinc-800
              ${isMobile ? 'p-6' : 'p-4'}
            `}
          >
            {isMobile && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowLegend(false)}
                className="absolute top-2 right-2 h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            )}
            
            <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <Info className="h-3 w-3" />
              App Colors
            </h3>
            <div className="space-y-1">
              {Object.entries({
                "claude": "#8b5cf6",
                "twitter": "#3b82f6",
                "jean memory": "#10b981",
                "cursor": "#f59e0b",
                "windsurf": "#ef4444",
                "chatgpt": "#06b6d4"
              }).map(([app, color]) => (
                <div key={app} className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-xs text-zinc-400 capitalize">{app}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3D Canvas */}
      <Canvas 
        camera={{ 
          position: isMobile ? [0, 5, 15] : [0, 5, 20], 
          fov: isMobile ? 75 : 60 
        }}
        gl={{ 
          antialias: !isMobile, 
          alpha: false,
          powerPreference: isMobile ? "low-power" : "high-performance"
        }}
        dpr={isMobile ? [1, 1] : [1, 2]}
      >
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={0.8} />
        <pointLight position={[-10, -10, -10]} intensity={0.4} color="#8b5cf6" />
        
        {!isMobile && <AnimatedParticles />}
        <GraphNodes nodes={nodes} onNodeClick={handleNodeClick} />
        
        <OrbitControls
          enablePan={!isMobile}
          enableZoom={true}
          enableRotate={true}
          autoRotate={!isMobile}
          autoRotateSpeed={0.3}
          minDistance={isMobile ? 3 : 5}
          maxDistance={isMobile ? 30 : 50}
        />
        
        <fog attach="fog" args={["#0a0a0a", isMobile ? 15 : 20, isMobile ? 40 : 60]} />
      </Canvas>

      {/* Selected Memory Details */}
      {selectedNode && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`
            absolute z-10
            ${isMobile 
              ? 'bottom-0 left-0 right-0 max-h-[40vh] overflow-y-auto' 
              : 'bottom-4 left-4 right-4 max-w-2xl mx-auto'
            }
            bg-zinc-900/95 backdrop-blur-sm rounded-t-lg lg:rounded-lg 
            p-4 border border-zinc-800
          `}
        >
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-lg font-semibold text-white">Selected Memory</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-zinc-400 hover:text-white text-xl"
            >
              ✕
            </button>
          </div>
          <p className="text-sm text-zinc-300 mb-3">{selectedNode.memory?.memory || "No content available"}</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-zinc-500">
              {selectedNode.memory?.created_at ? new Date(selectedNode.memory.created_at).toLocaleString() : "Unknown date"}
            </span>
            {selectedNode.memory?.app_name && (
              <span className="px-2 py-1 rounded-full bg-zinc-800 text-zinc-300">
                {selectedNode.memory.app_name}
              </span>
            )}
            {selectedNode.memory?.categories?.map((cat: string) => (
              <span key={cat} className="px-2 py-1 rounded-full bg-purple-900/30 text-purple-300">
                {cat}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
} 