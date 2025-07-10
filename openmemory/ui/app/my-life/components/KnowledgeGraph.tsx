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
import { RefreshCw, Info, Settings, X, Loader2 } from "lucide-react";
import { constants } from "@/components/shared/source-app";
import { GraphRenderer } from "./GraphRenderer";
import { GraphNode, GraphEdge } from './graph-types';

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
              emissiveIntensity={hovered === node.id ? 0.6 : 0.2}
              roughness={0.3}
              metalness={0.1}
              transparent
              opacity={hovered === node.id ? 1 : 0.8}
            />
          </Sphere>
          {hovered === node.id && (
            <Html distanceFactor={10}>
              <div className="bg-card/90 text-card-foreground p-3 rounded-lg text-xs max-w-xs shadow-xl border border-border">
                <p className="font-semibold mb-1 text-sm">{node.memory?.app_name || "Unknown"}</p>
                <p className="line-clamp-3 mb-2 text-muted-foreground">{node.memory?.memory || "No content"}</p>
                <div className="flex flex-wrap gap-1 text-muted-foreground/80">
                  <span>{node.memory?.created_at ? new Date(node.memory.created_at).toLocaleDateString() : ""}</span>
                  {node.memory?.categories?.length > 0 && (
                    <>
                      <span>•</span>
                      <span className="text-primary/80">{node.memory.categories.join(", ")}</span>
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
        color="hsl(var(--primary))"
        transparent
        opacity={0.3}
        sizeAttenuation
      />
    </points>
  );
}

export default function KnowledgeGraph({ onMemorySelect }: KnowledgeGraphProps) {
  const { memories, fetchMemories, isLoading } = useMemoriesApi();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedApp, setSelectedApp] = useState<string>("all");
  const [memoryLimit, setMemoryLimit] = useState<number>(60);
  const [clusterStrength, setClusterStrength] = useState<number>(1);
  const [apps, setApps] = useState<string[]>([]);
  const [showControls, setShowControls] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);

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
    fetchMemories(undefined, 1, 100).then(() => {
      setHasFetched(true);
    });
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
        "claude": "hsl(240, 70%, 70%)",       // Muted Blue
        "twitter": "hsl(200, 80%, 70%)",      // Lighter Blue
        "jean memory": "hsl(150, 60%, 60%)",  // Seafoam Green
        "cursor": "hsl(45, 80%, 70%)",        // Soft Yellow
        "windsurf": "hsl(0, 70%, 70%)",       // Muted Red
        "chatgpt": "hsl(180, 60%, 60%)",      // Cyan
      };
      const color = appColors[memory.app_name?.toLowerCase()] || "hsl(var(--muted-foreground))";
      
      // Size based on content length
      const size = Math.min(Math.max(memory.memory?.length / 800 || 0.1, 0.1), 0.3);
      
      return {
        id: memory.id,
        position: positions[index].clone().add(new THREE.Vector3(Math.random()-0.5, Math.random()-0.5, Math.random()-0.5)),
        targetPosition: positions[index],
        memory,
        color,
        size
      };
    });
    
    setNodes(graphNodes);

    // --- Create Edges ---
    const graphEdges: GraphEdge[] = [];
    const appGroups: { [key: string]: string[] } = {};
    graphNodes.forEach(node => {
      const appName = node.memory.app_name || 'unknown';
      if (!appGroups[appName]) appGroups[appName] = [];
      appGroups[appName].push(node.id);
    });

    Object.values(appGroups).forEach(group => {
      if (group.length > 1) {
        for (let i = 0; i < group.length; i++) {
          for (let j = i + 1; j < group.length; j++) {
            // Limit number of edges to avoid clutter
            if (Math.random() > 0.8) {
              graphEdges.push({ source: group[i], target: group[j] });
            }
          }
        }
      }
    });
    setEdges(graphEdges);

  }, [memories, selectedApp, memoryLimit, clusterStrength]);

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    onMemorySelect(node.id);
  };

  const handleRefresh = () => {
    fetchMemories(undefined, 1, 100);
  };

  return (
    <div className="relative w-full h-full bg-background overflow-hidden">
      {/* Loading State */}
      {isLoading && !hasFetched && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-background/50 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin" />
            <p>Loading your universe...</p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && hasFetched && memories.length === 0 && (
        <div className="absolute inset-0 z-30 flex items-center justify-center">
          <div className="text-center">
            <h3 className="text-2xl font-semibold text-foreground mb-2">Your Universe Awaits</h3>
            <p className="text-muted-foreground mb-4">
              It looks like you don't have any memories yet.
            </p>
            <Button onClick={handleRefresh}>
              <RefreshCw className="w-4 h-4 mr-2"/>
              Check for Memories
            </Button>
          </div>
        </div>
      )}

      {/* Mobile Control Buttons */}
      {isMobile && memories.length > 0 && (
        <div className="absolute top-2 left-2 right-2 z-20 flex justify-between">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowControls(!showControls)}
            className="h-8 w-8 bg-card/90 backdrop-blur-sm"
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowLegend(!showLegend)}
            className="h-8 w-8 bg-card/90 backdrop-blur-sm"
          >
            <Info className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Control Panel */}
      <AnimatePresence>
        {(!isMobile || showControls) && memories.length > 0 && (
          <motion.div
            initial={{ opacity: 0, x: isMobile ? -100 : 0, y: isMobile ? 0 : -20 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: isMobile ? -100 : 0 }}
            className={`
              absolute z-10
              ${isMobile ? 'inset-0 bg-background/95' : 'top-4 left-4 bg-card/80'}
              backdrop-blur-lg rounded-lg border border-border/80 shadow-2xl
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
                <h2 className={`${isMobile ? 'text-2xl' : 'text-xl'} font-semibold text-foreground`}>
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
              
              <p className="text-sm text-muted-foreground">
                {nodes.length} memories visualized
              </p>
              
              {/* App Filter */}
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground">Filter by App</label>
                <Select value={selectedApp} onValueChange={setSelectedApp}>
                  <SelectTrigger className={`${isMobile ? 'w-full' : 'w-48'}`}>
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
                <label className="text-xs text-muted-foreground">
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
                <label className="text-xs text-muted-foreground">
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
        {(!isMobile || showLegend) && memories.length > 0 && (
          <motion.div
            initial={{ opacity: 0, x: isMobile ? 100 : 0, y: isMobile ? 0 : -20 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={{ opacity: 0, x: isMobile ? 100 : 0 }}
            transition={{ delay: isMobile ? 0 : 0.2 }}
            className={`
              absolute z-10
              ${isMobile ? 'inset-0 bg-background/95' : 'top-4 right-4 bg-card/80'}
              backdrop-blur-lg rounded-lg border border-border/80 shadow-2xl
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
            
            <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
              <Info className="h-3 w-3" />
              App Colors
            </h3>
            <div className="space-y-1">
              {Object.entries({
                "claude": "hsl(240, 70%, 70%)",
                "twitter": "hsl(200, 80%, 70%)",
                "jean memory": "hsl(150, 60%, 60%)",
                "cursor": "hsl(45, 80%, 70%)",
                "windsurf": "hsl(0, 70%, 70%)",
                "chatgpt": "hsl(180, 60%, 60%)",
              }).map(([app, color]) => (
                <div key={app} className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-xs text-muted-foreground capitalize">{app}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3D Canvas */}
      <Canvas 
        className={memories.length === 0 ? 'opacity-0' : 'opacity-100 transition-opacity duration-500'}
        camera={{ 
          position: isMobile ? [0, 2, 8] : [0, 3, 12], 
          fov: isMobile ? 75 : 60 
        }}
        gl={{ 
          antialias: !isMobile, 
          alpha: true,
          powerPreference: isMobile ? "low-power" : "high-performance"
        }}
        dpr={isMobile ? [1, 1] : [1, 2]}
      >
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={0.8} />
        <pointLight position={[-10, -10, -10]} intensity={0.4} color="hsl(var(--primary))" />
        
        {!isMobile && <AnimatedParticles />}
        <GraphRenderer 
          nodes={nodes}
          edges={edges}
          hovered={hoveredNode}
          setHovered={setHoveredNode}
          onNodeClick={handleNodeClick}
          isMobile={isMobile}
        />
        
        <OrbitControls
          enablePan={!isMobile}
          enableZoom={true}
          enableRotate={true}
          autoRotate={!isMobile}
          autoRotateSpeed={0.3}
          minDistance={isMobile ? 3 : 5}
          maxDistance={isMobile ? 30 : 50}
        />
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
            bg-card/80 backdrop-blur-lg rounded-t-lg lg:rounded-lg 
            p-4 border-t lg:border border-border/80 shadow-2xl
          `}
        >
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-lg font-semibold text-foreground">Selected Memory</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-muted-foreground hover:text-foreground text-xl"
            >
              ✕
            </button>
          </div>
          <p className="text-sm text-muted-foreground mb-3">{selectedNode.memory?.memory || "No content available"}</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="text-muted-foreground/80">
              {selectedNode.memory?.created_at ? new Date(selectedNode.memory.created_at).toLocaleString() : "Unknown date"}
            </span>
            {selectedNode.memory?.app_name && (
              <span className="px-2 py-1 rounded-full bg-muted text-muted-foreground">
                {selectedNode.memory.app_name}
              </span>
            )}
            {selectedNode.memory?.categories?.map((cat: string) => (
              <span key={cat} className="px-2 py-1 rounded-full bg-primary/10 text-primary">
                {cat}
              </span>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
} 