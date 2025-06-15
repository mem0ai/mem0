"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, Sphere, Line, Html } from "@react-three/drei";
import * as THREE from "three";
import { GraphNode, GraphEdge } from './graph-types';

interface GraphNodesProps {
    nodes: GraphNode[];
    hovered: string | null;
    setHovered: (id: string | null) => void;
    onNodeClick: (node: GraphNode) => void;
}

const NodeComponent = ({ node, hovered, setHovered, onNodeClick }: { node: GraphNode; } & Omit<GraphNodesProps, 'nodes'>) => {
    useFrame((state, delta) => {
        // Gentle floating animation
        const time = state.clock.getElapsedTime();
        node.position.x += Math.sin(time * node.id.charCodeAt(0) * 0.001) * delta * 0.1;
        node.position.y += Math.cos(time * node.id.charCodeAt(1) * 0.001) * delta * 0.1;
        node.position.z += Math.sin(time * node.id.charCodeAt(2) * 0.001) * delta * 0.1;

        // Move towards target
        node.position.lerp(node.targetPosition, 0.02);
    });

    return (
        <group position={node.position}>
            <Sphere
                args={[node.size, 16, 16]}
                onClick={() => onNodeClick(node)}
                onPointerOver={(e) => { e.stopPropagation(); setHovered(node.id); }}
                onPointerOut={() => setHovered(null)}
            >
                <meshPhysicalMaterial
                    color={node.color}
                    emissive={node.color}
                    emissiveIntensity={hovered === node.id ? 0.5 : 0.1}
                    roughness={0.4}
                    metalness={0.1}
                    transparent
                    opacity={hovered === node.id ? 1.0 : 0.7}
                />
            </Sphere>
            {hovered === node.id && (
                <Html distanceFactor={10} zIndexRange={[100, 0]}>
                    <div className="bg-card/90 text-card-foreground p-3 rounded-lg text-xs max-w-xs shadow-xl border border-border backdrop-blur-sm">
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
    );
}

const GraphNodes = ({ nodes, hovered, setHovered, onNodeClick }: GraphNodesProps) => {
    return (
        <>
            {nodes.map((node) => <NodeComponent key={node.id} node={node} hovered={hovered} setHovered={setHovered} onNodeClick={onNodeClick} />)}
        </>
    );
}


function GraphEdges({ edges, nodes }: { edges: GraphEdge[], nodes: GraphNode[] }) {
    const lines = useMemo(() => {
        const lineGeometries: { start: THREE.Vector3, end: THREE.Vector3, id: string }[] = [];
        edges.forEach(edge => {
            const startNode = nodes.find(n => n.id === edge.source);
            const endNode = nodes.find(n => n.id === edge.target);
            if (startNode && endNode) {
                lineGeometries.push({ start: startNode.position, end: endNode.position, id: `${edge.source}-${edge.target}` });
            }
        });
        return lineGeometries;
    }, [edges, nodes]);

    return (
        <>
            {lines.map(line => (
                <Line
                    key={line.id}
                    points={[line.start, line.end]}
                    color="hsl(var(--muted-foreground))"
                    lineWidth={0.5}
                    transparent
                    opacity={0.15}
                />
            ))}
        </>
    );
}

function AnimatedParticles() {
  const particlesRef = useRef<THREE.Points>(null);
  const count = 100;

  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) {
      pos[i] = (Math.random() - 0.5) * 50;
    }
    return pos;
  }, []);

  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = state.clock.getElapsedTime() * 0.01;
    }
  });

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.02} color="hsl(var(--primary))" transparent opacity={0.4} />
    </points>
  );
}

export const GraphRenderer = ({ nodes, edges, hovered, setHovered, onNodeClick, isMobile }: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    hovered: string | null;
    setHovered: (id: string | null) => void;
    onNodeClick: (node: GraphNode) => void;
    isMobile: boolean;
}) => {
    return (
        <>
            <ambientLight intensity={0.6} />
            <pointLight position={[10, 10, 10]} intensity={1.0} />
            <pointLight position={[-10, -10, -10]} intensity={0.5} color="hsl(var(--primary))" />
            
            {!isMobile && <AnimatedParticles />}
            <GraphNodes nodes={nodes} hovered={hovered} setHovered={setHovered} onNodeClick={onNodeClick} />
            <GraphEdges edges={edges} nodes={nodes} />
        </>
    )
} 