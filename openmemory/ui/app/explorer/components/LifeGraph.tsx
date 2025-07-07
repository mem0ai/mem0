"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html, Sphere, Text } from "@react-three/drei";
import * as THREE from "three";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Search, RefreshCw, Settings, Users, MapPin, BookOpen, ChartLine } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface GraphNode {
  id: string;
  type: 'memory' | 'entity' | 'temporal_pattern';
  name?: string;
  content?: string;
  entity_type?: string;
  position: { x: number; y: number; z: number };
  size: number;
  source?: string;
  timestamp?: string;
  strength?: number;
  extraction_method?: string;
  memory_count?: number;
  confidence?: number;
  period?: string;
  themes?: string[];
  score?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
  strength: number;
}

interface LifeGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters: any[];
  metadata: {
    total_memories: number;
    total_nodes: number;
    total_edges: number;
    focus_query?: string;
    generated_at: string;
    graph_entities_found: number;
    enhanced_entities_extracted: number;
    temporal_patterns_identified: number;
    ai_insights: any[];
    search_method: string;
    capabilities_used: any;
  };
}

// 3D Node component
function GraphNode3D({ 
  node, 
  isHovered, 
  isSelected, 
  onClick, 
  onHover 
}: { 
  node: GraphNode;
  isHovered: boolean;
  isSelected: boolean;
  onClick: (node: GraphNode) => void;
  onHover: (node: GraphNode | null) => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state, delta) => {
    if (meshRef.current) {
      // Gentle floating animation
      meshRef.current.rotation.y += delta * 0.5;
      
      if (isHovered || isSelected) {
        meshRef.current.scale.lerp(new THREE.Vector3(1.2, 1.2, 1.2), 0.1);
      } else {
        meshRef.current.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
      }
    }
  });

  const getNodeColor = (node: GraphNode) => {
    if (node.type === 'entity') {
      // Enhanced entity colors based on extraction method and type
      const baseColors = {
        person: '#60a5fa', // Blue
        place: '#34d399', // Green
        topic: '#f59e0b', // Orange
        organization: '#8b5cf6', // Purple
        unknown: '#a78bfa' // Light purple
      };
      
      const baseColor = baseColors[node.entity_type as keyof typeof baseColors] || baseColors.unknown;
      
      // Return solid colors for THREE.js compatibility
      if (node.extraction_method === 'graphiti_graph') {
        return baseColor; // Full color for graph entities
      } else if (node.extraction_method === 'ai_synthesis') {
        // Use slightly different but valid hex colors for AI-extracted
        const aiColors = {
          person: '#93c5fd', // Lighter blue
          place: '#6ee7b7', // Lighter green
          topic: '#fbbf24', // Lighter orange
          organization: '#a78bfa', // Lighter purple
          unknown: '#c4b5fd' // Lighter light purple
        };
        return aiColors[node.entity_type as keyof typeof aiColors] || aiColors.unknown;
      } else {
        // Use even lighter colors for other methods
        const lightColors = {
          person: '#dbeafe', // Very light blue
          place: '#d1fae5', // Very light green
          topic: '#fef3c7', // Very light orange
          organization: '#e0e7ff', // Very light purple
          unknown: '#f3f4f6' // Very light gray
        };
        return lightColors[node.entity_type as keyof typeof lightColors] || lightColors.unknown;
      }
    }
    
    if (node.type === 'temporal_pattern') {
      return '#ef4444'; // Red for temporal patterns
    }
    
    // Memory nodes - color by source
    const sourceColors: { [key: string]: string } = {
      'claude': '#8b5cf6',
      'chatgpt': '#10b981', 
      'cursor': '#f59e0b',
      'windsurf': '#ef4444',
      'jean memory': '#06b6d4',
      'jean memory v2': '#06b6d4',
      'twitter': '#3b82f6',
      'mem0': '#10b981',
      'graphiti': '#8b5cf6'
    };
    
    return sourceColors[node.source?.toLowerCase() || ''] || '#64748b';
  };

  // Enhanced node size calculation
  const getNodeSize = (node: GraphNode) => {
    if (node.type === 'entity') {
      // Size based on strength and extraction method
      let baseSize = Math.min(Math.max((node.strength || 1) / 3, 0.4), 1.8);
      
      // Boost size for graph-extracted entities
      if (node.extraction_method === 'graphiti_graph') {
        baseSize *= 1.2;
      }
      
      return baseSize;
    }
    
    if (node.type === 'temporal_pattern') {
      return Math.min(Math.max((node.memory_count || 1) / 4, 0.5), 1.5);
    }
    
    // Memory nodes
    return Math.min(Math.max((node.content?.length || 100) / 100, 0.5), 2.0);
  };

  return (
    <group 
      position={[node.position.x, node.position.y, node.position.z]}
      onClick={() => onClick(node)}
      onPointerOver={() => onHover(node)}
      onPointerOut={() => onHover(null)}
    >
      <Sphere
        ref={meshRef}
        args={[getNodeSize(node), 16, 16]}
      >
        <meshPhysicalMaterial
          color={getNodeColor(node)}
          emissive={getNodeColor(node)}
          emissiveIntensity={isHovered || isSelected ? 0.4 : 0.1}
          roughness={0.3}
          metalness={0.1}
          transparent
          opacity={0.8}
        />
      </Sphere>
      
      {(isHovered || isSelected) && (
        <Html distanceFactor={15}>
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-card/95 text-card-foreground p-3 rounded-lg text-xs max-w-xs shadow-xl border border-border backdrop-blur-sm"
          >
            <div className="flex items-center gap-2 mb-2">
              {node.type === 'entity' && (
                <>
                  {node.entity_type === 'person' && <Users className="h-3 w-3" />}
                  {node.entity_type === 'place' && <MapPin className="h-3 w-3" />}
                  {node.entity_type === 'topic' && <BookOpen className="h-3 w-3" />}
                  {node.entity_type === 'organization' && <Settings className="h-3 w-3" />}
                </>
              )}
              {node.type === 'temporal_pattern' && <ChartLine className="h-3 w-3" />}
              
              <Badge variant="outline" className="text-xs">
                {node.type === 'entity' ? node.entity_type : 
                 node.type === 'temporal_pattern' ? 'time pattern' : node.source}
              </Badge>
              
              {/* Extraction method indicator for entities */}
              {node.type === 'entity' && node.extraction_method && (
                <Badge variant="secondary" className="text-xs">
                  {node.extraction_method === 'graphiti_graph' ? 'graph' :
                   node.extraction_method === 'ai_synthesis' ? 'AI' : 'basic'}
                </Badge>
              )}
            </div>
            
            <h4 className="font-semibold mb-1">
              {node.type === 'entity' ? node.name : 
               node.type === 'temporal_pattern' ? `${node.period}` : 'Memory'}
            </h4>
            
            {node.type === 'entity' ? (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs">
                  Found in {node.strength} {node.strength === 1 ? 'memory' : 'memories'}
                </p>
                {node.confidence && (
                  <p className="text-muted-foreground text-xs">
                    Confidence: {(node.confidence * 100).toFixed(0)}%
                  </p>
                )}
                {node.extraction_method === 'graphiti_graph' && (
                  <p className="text-green-600 text-xs">✓ Graph verified</p>
                )}
              </div>
            ) : node.type === 'temporal_pattern' ? (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs">
                  {node.memory_count} memories in this period
                </p>
                {node.themes && (
                  <p className="text-muted-foreground text-xs">
                    Themes: {Array.isArray(node.themes) ? node.themes.join(', ') : node.themes}
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-muted-foreground text-xs line-clamp-3">
                  {node.content || 'Memory content'}
                </p>
                {node.timestamp && (
                  <p className="text-muted-foreground text-xs">
                    {new Date(node.timestamp).toLocaleDateString()}
                  </p>
                )}
                {node.score && (
                  <p className="text-muted-foreground text-xs">
                    Score: {(node.score * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            )}
          </motion.div>
        </Html>
      )}
    </group>
  );
}

// Connection lines between nodes
function GraphEdges({ edges, nodes }: { edges: GraphEdge[]; nodes: GraphNode[] }) {
  const nodePositions = useMemo(() => {
    const positions: { [key: string]: THREE.Vector3 } = {};
    nodes.forEach(node => {
      positions[node.id] = new THREE.Vector3(
        node.position.x,
        node.position.y,
        node.position.z
      );
    });
    return positions;
  }, [nodes]);

  return (
    <>
      {edges.map((edge, index) => {
        const sourcePos = nodePositions[edge.source];
        const targetPos = nodePositions[edge.target];
        
        if (!sourcePos || !targetPos) return null;

        const points = [sourcePos, targetPos];
        
        return (
          <line key={`${edge.source}-${edge.target}-${index}`}>
            <bufferGeometry>
              <bufferAttribute
                attach="attributes-position"
                args={[new Float32Array(points.flatMap(p => [p.x, p.y, p.z])), 3]}
              />
            </bufferGeometry>
            <lineBasicMaterial
              color="#4a5568"
              transparent
              opacity={0.3}
              linewidth={edge.strength * 2}
            />
          </line>
        );
      })}
    </>
  );
}

// Simple local processing functions for life graph data
const extractEntitiesFromContent = (content: string): Array<{ name: string; type: string; confidence: number }> => {
  const entities: Array<{ name: string; type: string; confidence: number }> = [];
  
  // Simple regex patterns for entity extraction
  const patterns = {
    person: [
      /\b[A-Z][a-z]+ [A-Z][a-z]+\b/g, // Full names
      /\b(?:met|talked to|called|texted|saw|visited|with) ([A-Z][a-z]+)\b/gi, // Names after verbs
    ],
    place: [
      /\bin ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b/gi, // Places after "in"
      /\bat ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b/gi, // Places after "at"
      /\bwent to ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b/gi, // Places after "went to"
    ],
    topic: [
      /\b(work|job|career|project|meeting|presentation|interview|startup|company)\b/gi, // Work-related
      /\b(family|friends|relationship|dating|marriage|wedding|parents|children)\b/gi, // Personal
      /\b(exercise|workout|fitness|running|gym|sport|health|meditation)\b/gi, // Health
      /\b(travel|vacation|trip|flight|hotel|restaurant|food|dinner)\b/gi, // Travel & Food
      /\b(book|movie|music|art|learning|course|education|study)\b/gi, // Learning & Culture
    ]
  };

  for (const [entityType, patternList] of Object.entries(patterns)) {
    for (const pattern of patternList) {
      const matches = content.match(pattern) || [];
      for (const match of matches) {
        let cleanMatch = match.trim();
        
        // Clean up matches from verb patterns
        if (entityType === 'person' && (match.includes('met ') || match.includes('talked to ') || match.includes('with '))) {
          cleanMatch = match.replace(/^.*?(met |talked to |called |texted |saw |visited |with )/, '');
        }
        if (entityType === 'place' && (match.includes('in ') || match.includes('at ') || match.includes('went to '))) {
          cleanMatch = match.replace(/^.*?(in |at |went to )/, '');
        }
        
        if (cleanMatch && cleanMatch.length > 2) {
          entities.push({
            name: cleanMatch.trim(),
            type: entityType,
            confidence: 0.7
          });
        }
      }
    }
  }

  // Remove duplicates
  const uniqueEntities = entities.filter((entity, index, self) => 
    index === self.findIndex(e => e.name.toLowerCase() === entity.name.toLowerCase() && e.type === entity.type)
  );

  return uniqueEntities.slice(0, 10); // Limit to 10 entities per memory
};

const processMemoriesLocally = (memories: any[], focusQuery?: string): LifeGraphData => {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const entityGroups: { [key: string]: { name: string; type: string; memories: string[]; strength: number } } = {};

  // Filter memories by focus query if provided
  const filteredMemories = focusQuery 
    ? memories.filter(mem => 
        mem.memory?.toLowerCase().includes(focusQuery.toLowerCase()) ||
        mem.content?.toLowerCase().includes(focusQuery.toLowerCase())
      )
    : memories;

  // Process each memory
  filteredMemories.forEach((memory, index) => {
    const content = memory.memory || memory.content || '';
    if (!content || content.length < 10) return;

    // Create memory node
    const memoryNode: GraphNode = {
      id: `memory_${index}`,
      type: 'memory',
      content: content.trim(),
      source: memory.app_name || 'unknown',
      timestamp: memory.created_at ? new Date(memory.created_at).toISOString() : undefined,
      size: Math.min(Math.max(content.length / 100, 0.5), 2.0),
      position: {
        x: (Math.random() - 0.5) * 20,
        y: (Math.random() - 0.5) * 20,
        z: (Math.random() - 0.5) * 20
      }
    };

    // Extract entities
    const entities = extractEntitiesFromContent(content);
    
    // Process entities
    entities.forEach(entity => {
      const entityId = `entity_${entity.name.toLowerCase().replace(/\s+/g, '_')}`;
      
      if (!entityGroups[entityId]) {
        entityGroups[entityId] = {
          name: entity.name,
          type: entity.type,
          memories: [],
          strength: 0
        };
      }
      
      entityGroups[entityId].memories.push(memoryNode.id);
      entityGroups[entityId].strength += 1;
      
      // Create edge
      edges.push({
        source: memoryNode.id,
        target: entityId,
        type: 'contains',
        strength: entity.confidence
      });
    });

    nodes.push(memoryNode);
  });

  // Add entity nodes (only those mentioned multiple times)
  Object.entries(entityGroups).forEach(([entityId, entityData]) => {
    if (entityData.strength >= 2) {
      const entityNode: GraphNode = {
        id: entityId,
        type: 'entity',
        name: entityData.name,
        entity_type: entityData.type,
        strength: entityData.strength,
        size: Math.min(Math.max(entityData.strength / 2, 0.3), 1.5),
        position: {
          x: (Math.random() - 0.5) * 20,
          y: (Math.random() - 0.5) * 20,
          z: (Math.random() - 0.5) * 20
        }
      };
      nodes.push(entityNode);
    }
  });

  // Simple force-directed layout adjustment
  for (let iteration = 0; iteration < 50; iteration++) {
    const forces: { [id: string]: { x: number; y: number; z: number } } = {};
    
    // Initialize forces
    nodes.forEach(node => {
      forces[node.id] = { x: 0, y: 0, z: 0 };
    });

    // Repulsive forces
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const node1 = nodes[i];
        const node2 = nodes[j];
        
        const dx = node1.position.x - node2.position.x;
        const dy = node1.position.y - node2.position.y;
        const dz = node1.position.z - node2.position.z;
        
        const distance = Math.sqrt(dx*dx + dy*dy + dz*dz) + 0.01;
        const force = 3.0 / (distance * distance);
        
        forces[node1.id].x += (dx / distance) * force;
        forces[node1.id].y += (dy / distance) * force;
        forces[node1.id].z += (dz / distance) * force;
        
        forces[node2.id].x -= (dx / distance) * force;
        forces[node2.id].y -= (dy / distance) * force;
        forces[node2.id].z -= (dz / distance) * force;
      }
    }

    // Attractive forces for connected nodes
    edges.forEach(edge => {
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      
      if (source && target) {
        const dx = target.position.x - source.position.x;
        const dy = target.position.y - source.position.y;
        const dz = target.position.z - source.position.z;
        
        const distance = Math.sqrt(dx*dx + dy*dy + dz*dz) + 0.01;
        const force = distance * 0.03 * edge.strength;
        
        forces[source.id].x += (dx / distance) * force;
        forces[source.id].y += (dy / distance) * force;
        forces[source.id].z += (dz / distance) * force;
        
        forces[target.id].x -= (dx / distance) * force;
        forces[target.id].y -= (dy / distance) * force;
        forces[target.id].z -= (dz / distance) * force;
      }
    });

    // Apply forces with damping
    const damping = 0.1;
    nodes.forEach(node => {
      node.position.x += forces[node.id].x * damping;
      node.position.y += forces[node.id].y * damping;
      node.position.z += forces[node.id].z * damping;
    });
  }

  return {
    nodes,
    edges,
    clusters: [], // Simple implementation doesn't include complex clustering
    metadata: {
      total_memories: filteredMemories.length,
      total_nodes: nodes.length,
      total_edges: edges.length,
      focus_query: focusQuery,
      generated_at: new Date().toISOString(),
      graph_entities_found: 0,
      enhanced_entities_extracted: 0,
      temporal_patterns_identified: 0,
      ai_insights: [],
      search_method: 'local_processing',
      capabilities_used: {}
    }
  };
};

// Main Life Graph component
export function LifeGraph({ memories, deepQueryButton }: { memories: any[]; deepQueryButton?: React.ReactElement }) {
  const { user, accessToken } = useAuth();
  const [graphData, setGraphData] = useState<LifeGraphData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [focusQuery, setFocusQuery] = useState("");
  const [cachedData, setCachedData] = useState<{ [key: string]: LifeGraphData }>({});
  const [useEnhancedSearch, setUseEnhancedSearch] = useState(true);

  // Enhanced processing using Jean Memory V2 API
  const processGraphDataEnhanced = async (query?: string) => {
    if (!accessToken) {
      console.error("No access token available");
      return;
    }

    setIsLoading(true);
    
    // Check cache first
    const cacheKey = `enhanced_${query || 'all'}_${memories.length}`;
    if (cachedData[cacheKey]) {
      setGraphData(cachedData[cacheKey]);
      setIsLoading(false);
      return;
    }
    
    try {
      // Use localhost API directly - no complex URL manipulation
      const apiUrl = 'http://localhost:8765';
      
      const params = new URLSearchParams({
        limit: '50',
        include_entities: 'true',
        include_temporal_clusters: 'true',
        use_cache: 'true'
      });
      
      if (query) {
        params.append('focus_query', query);
      }
      
      const url = `${apiUrl}/api/v1/memories/life-graph-data?${params}`;
      console.log('🚀 Attempting enhanced search API call:', url);
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      console.log('📡 Enhanced API response status:', response.status);
      
      if (response.ok) {
        const enhancedData = await response.json();
        console.log('📊 Enhanced API response data:', enhancedData);
        
        // Convert enhanced data to our expected format
        const processedData: LifeGraphData = {
          nodes: enhancedData.nodes || [],
          edges: enhancedData.edges || [],
          clusters: enhancedData.clusters || [],
          metadata: {
            total_memories: enhancedData.metadata?.total_memories || 0,
            total_nodes: enhancedData.nodes?.length || 0,
            total_edges: enhancedData.edges?.length || 0,
            focus_query: query,
            generated_at: enhancedData.metadata?.generated_at || new Date().toISOString(),
            // Enhanced metadata
            graph_entities_found: enhancedData.metadata?.graph_entities_found || 0,
            enhanced_entities_extracted: enhancedData.metadata?.enhanced_entities_extracted || 0,
            temporal_patterns_identified: enhancedData.metadata?.temporal_patterns_identified || 0,
            ai_insights: enhancedData.metadata?.ai_insights || [],
            search_method: enhancedData.metadata?.search_method || 'enhanced_graph_hybrid',
            capabilities_used: enhancedData.metadata?.capabilities_used || {}
          }
        };
        
        setGraphData(processedData);
        
        // Cache the result
        setCachedData(prev => ({ ...prev, [cacheKey]: processedData }));
        
        console.log('✅ Enhanced graph data loaded successfully:', {
          nodes: processedData.nodes.length,
          edges: processedData.edges.length,
          searchMethod: processedData.metadata.search_method,
          capabilities: processedData.metadata.capabilities_used
        });
        
      } else {
        const errorText = await response.text();
        console.error('❌ Enhanced API call failed:', {
          status: response.status,
          statusText: response.statusText,
          error: errorText
        });
        setUseEnhancedSearch(false);
        processGraphDataLocal(query);
      }
      
    } catch (err) {
      console.error('❌ Enhanced search failed with exception:', err);
      setUseEnhancedSearch(false);
      processGraphDataLocal(query);
    } finally {
      setIsLoading(false);
    }
  };

  // Fallback local processing (original implementation)
  const processGraphDataLocal = (query?: string) => {
    setIsLoading(true);
    
    const cacheKey = `local_${query || 'all'}_${memories.length}`;
    if (cachedData[cacheKey]) {
      setGraphData(cachedData[cacheKey]);
      setIsLoading(false);
      return;
    }
    
    try {
      // Process memories locally - no API call needed!
      const processedData = processMemoriesLocally(memories, query);
      setGraphData(processedData);
      
      // Cache the result
      setCachedData(prev => ({ ...prev, [cacheKey]: processedData }));
    } catch (err) {
      console.error('Failed to process graph data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Main processing function that chooses enhanced or local
  const processGraphData = (query?: string) => {
    if (useEnhancedSearch && accessToken) {
      processGraphDataEnhanced(query);
    } else {
      processGraphDataLocal(query);
    }
  };

  // Process data when memories change
  useEffect(() => {
    if (memories.length > 0) {
      processGraphData();
    }
  }, [memories.length, useEnhancedSearch, accessToken]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    processGraphData(focusQuery);
  };

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    console.log('Selected node:', node);
  };

  const handleNodeHover = (node: GraphNode | null) => {
    setHoveredNode(node);
  };

  // Enhanced stats calculation with graph insights
  const stats = useMemo(() => {
    if (!graphData || !graphData.nodes) return null;
    
    const entityCounts = graphData.nodes
      .filter(n => n.type === 'entity')
      .reduce((acc, node) => {
        const type = node.entity_type || 'unknown';
        acc[type] = (acc[type] || 0) + 1;
        return acc;
      }, {} as { [key: string]: number });
    
    const nodeTypeCounts = graphData.nodes.reduce((acc, node) => {
      acc[node.type] = (acc[node.type] || 0) + 1;
      return acc;
    }, {} as { [key: string]: number });

    return {
      totalMemories: nodeTypeCounts.memory || 0,
      totalEntities: nodeTypeCounts.entity || 0,
      totalTemporalPatterns: nodeTypeCounts.temporal_pattern || 0,
      totalConnections: graphData.edges.length,
      entityCounts,
      nodeTypeCounts,
      // Enhanced metadata
      searchMethod: graphData.metadata.search_method || 'local',
      graphEntitiesFound: graphData.metadata.graph_entities_found || 0,
      enhancedEntitiesExtracted: graphData.metadata.enhanced_entities_extracted || 0,
      temporalPatternsIdentified: graphData.metadata.temporal_patterns_identified || 0,
      capabilitiesUsed: graphData.metadata.capabilities_used || {},
      aiInsights: graphData.metadata.ai_insights || []
    };
  }, [graphData]);

  if (!user) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-muted-foreground">Please log in to view your Life Graph</p>
        </div>
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="relative w-full h-full bg-background overflow-hidden">
        {/* Blank canvas - no placeholder content */}
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-background overflow-hidden">
      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-muted-foreground">Generating your life graph...</p>
          </div>
        </div>
      )}

      {/* Error state removed - local processing doesn't fail like API calls */}

      {/* Top Left Controls - Focus Input + Stats */}
      <div className="absolute top-4 left-4 z-30 space-y-3">
        {/* Focus Search Input */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Focus on topic..."
            value={focusQuery}
            onChange={(e) => setFocusQuery(e.target.value)}
            className="w-48"
          />
          <Button type="submit" size="sm" disabled={isLoading}>
            <Search className="w-4 h-4" />
          </Button>
        </form>

        {/* Stats panel */}
        {stats && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-card/90 border border-border rounded-lg p-3 backdrop-blur-sm max-w-sm"
          >
            {/* Primary stats */}
            <div className="grid grid-cols-3 gap-3 text-center text-xs mb-3">
              <div>
                <div className="font-semibold text-primary">{stats.totalMemories}</div>
                <div className="text-muted-foreground">Memories</div>
              </div>
              <div>
                <div className="font-semibold text-primary">{stats.totalEntities}</div>
                <div className="text-muted-foreground">Entities</div>
              </div>
              <div>
                <div className="font-semibold text-primary">{stats.totalConnections}</div>
                <div className="text-muted-foreground">Links</div>
              </div>
            </div>
            
            {/* Enhanced features when available */}
            {stats.searchMethod && stats.searchMethod !== 'local_processing' && stats.searchMethod !== 'local' && (
              <div className="border-t border-border pt-3 mb-3">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {stats.totalTemporalPatterns > 0 && (
                    <div>
                      <div className="font-semibold text-primary">{stats.totalTemporalPatterns}</div>
                      <div className="text-muted-foreground">Time Patterns</div>
                    </div>
                  )}
                  {stats.graphEntitiesFound > 0 && (
                    <div>
                      <div className="font-semibold text-primary">{stats.graphEntitiesFound}</div>
                      <div className="text-muted-foreground">Graph Entities</div>
                    </div>
                  )}
                  {stats.aiInsights.length > 0 && (
                    <div>
                      <div className="font-semibold text-primary">{stats.aiInsights.length}</div>
                      <div className="text-muted-foreground">AI Insights</div>
                    </div>
                  )}
                  {Object.keys(stats.capabilitiesUsed).length > 0 && (
                    <div>
                      <div className="font-semibold text-primary">
                        {Object.values(stats.capabilitiesUsed).filter(Boolean).length}
                      </div>
                      <div className="text-muted-foreground">Capabilities</div>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Entity breakdown */}
            <div className="border-t border-border pt-3">
              <div className="flex flex-wrap gap-1">
                {Object.entries(stats.entityCounts).map(([type, count]) => (
                  <Badge key={type} variant="secondary" className="text-xs">
                    {type}: {count}
                  </Badge>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Top Right Controls - Deep Life Query */}
      <div className="absolute top-4 right-4 z-30">
        {deepQueryButton}
      </div>

      {/* Refresh button - Bottom Left */}
      <div className="absolute bottom-4 left-4 z-30 flex gap-2">
        <Button
          onClick={() => processGraphData(focusQuery)}
          variant="outline"
          size="sm"
          disabled={isLoading}
          className="bg-card/90 backdrop-blur-sm"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
        
        {/* Enhanced/Local toggle for debugging */}
        <Button
          onClick={() => {
            setUseEnhancedSearch(!useEnhancedSearch);
            // Clear cache when switching modes
            setCachedData({});
            // Reprocess with new mode
            setTimeout(() => processGraphData(focusQuery), 100);
          }}
          variant={useEnhancedSearch ? "default" : "secondary"}
          size="sm"
          disabled={isLoading}
          className="bg-card/90 backdrop-blur-sm text-xs"
          title={useEnhancedSearch ? "Switch to Local Processing" : "Switch to Enhanced Search"}
        >
          {useEnhancedSearch ? "Enhanced" : "Local"}
        </Button>
      </div>

      {/* 3D Canvas */}
      {graphData && (
        <Canvas
          camera={{ position: [0, 0, 20], fov: 60 }}
          gl={{ antialias: true, alpha: true }}
        >
          <ambientLight intensity={0.4} />
          <pointLight position={[10, 10, 10]} intensity={0.8} />
          <pointLight position={[-10, -10, -10]} intensity={0.4} color="#4f46e5" />
          
          {/* Render nodes */}
          {graphData.nodes.map(node => (
            <GraphNode3D
              key={node.id}
              node={node}
              isHovered={hoveredNode?.id === node.id}
              isSelected={selectedNode?.id === node.id}
              onClick={handleNodeClick}
              onHover={handleNodeHover}
            />
          ))}
          
          {/* Render edges */}
          <GraphEdges edges={graphData.edges} nodes={graphData.nodes} />
          
          {/* Controls */}
          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            autoRotate={false}
            minDistance={5}
            maxDistance={100}
            dampingFactor={0.05}
            enableDamping={true}
          />
        </Canvas>
      )}

      {/* Selected node details - Bottom Center, avoiding refresh button */}
      {selectedNode && (
        <div className="absolute bottom-4 left-20 right-4 z-30">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-card/95 border border-border rounded-lg p-4 backdrop-blur-sm max-w-md mx-auto"
          >
            <div className="flex justify-between items-start mb-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline">
                  {selectedNode.type === 'entity' ? selectedNode.entity_type : 
                   selectedNode.type === 'temporal_pattern' ? 'time pattern' : selectedNode.source}
                </Badge>
                <h4 className="font-semibold text-lg">
                  {selectedNode.type === 'entity' ? selectedNode.name : 
                   selectedNode.type === 'temporal_pattern' ? selectedNode.period : 'Memory'}
                </h4>
                
                {/* Additional badges for enhanced info */}
                {selectedNode.type === 'entity' && selectedNode.extraction_method && (
                  <Badge variant="secondary" className="text-xs">
                    {selectedNode.extraction_method === 'graphiti_graph' ? 'Graph Entity' :
                     selectedNode.extraction_method === 'ai_synthesis' ? 'AI Extracted' : 'Basic'}
                  </Badge>
                )}
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setSelectedNode(null)}
              >
                ×
              </Button>
            </div>
            
            {selectedNode.type === 'entity' ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  This {selectedNode.entity_type} appears in <span className="font-semibold text-primary">{selectedNode.strength}</span> {selectedNode.strength === 1 ? 'memory' : 'memories'}
                </p>
                
                {selectedNode.confidence && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Confidence:</span>
                    <div className="flex-1 bg-secondary rounded-full h-2">
                      <div 
                        className="bg-primary h-2 rounded-full transition-all" 
                        style={{ width: `${(selectedNode.confidence * 100)}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-muted-foreground">{(selectedNode.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                
                {selectedNode.extraction_method === 'graphiti_graph' && (
                  <p className="text-xs text-green-600 flex items-center gap-1">
                    <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                    Verified by knowledge graph
                  </p>
                )}
                
                <p className="text-xs text-muted-foreground">
                  Click to explore related memories and connections
                </p>
              </div>
            ) : selectedNode.type === 'temporal_pattern' ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  Time period with <span className="font-semibold text-primary">{selectedNode.memory_count}</span> memories
                </p>
                
                {selectedNode.themes && (
                  <div>
                    <p className="text-xs font-medium text-foreground mb-1">Key themes:</p>
                    <div className="flex flex-wrap gap-1">
                      {(Array.isArray(selectedNode.themes) ? selectedNode.themes : [selectedNode.themes]).map((theme, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {theme}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                <p className="text-xs text-muted-foreground">
                  Click to explore memories from this time period
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {selectedNode.content || 'Memory content'}
                </p>
                
                <div className="flex justify-between items-center text-xs text-muted-foreground">
                  {selectedNode.timestamp && (
                    <span>{new Date(selectedNode.timestamp).toLocaleDateString()}</span>
                  )}
                  {selectedNode.score && (
                    <span>Relevance: {(selectedNode.score * 100).toFixed(0)}%</span>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        </div>
      )}
    </div>
  );
} 