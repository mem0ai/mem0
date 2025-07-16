"use client";

import React, { useRef, useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { 
  Search, 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  Filter,
  Layers,
  Clock,
  Network,
  Brain,
  User,
  MapPin,
  Calendar,
  Hash,
  Package,
  Heart,
  Sparkles,
  RefreshCw,
  X,
  ChevronRight,
  Info
} from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

// Dynamic imports for client-side only
let cytoscape: any;
let cola: any;
let fcose: any;

// Initialize Cytoscape and extensions only on client-side
const initializeCytoscape = async () => {
  if (typeof window !== 'undefined' && !cytoscape) {
    cytoscape = (await import('cytoscape')).default;
    cola = (await import('cytoscape-cola')).default;
    fcose = (await import('cytoscape-fcose')).default;
    
    // Register layout extensions
    cytoscape.use(cola);
    cytoscape.use(fcose);
  }
  return cytoscape;
};

interface Memory {
  id: string;
  content: string;
  created_at: string;
  metadata?: any;
  source?: string;
}

interface Entity {
  id: string;
  type: 'Person' | 'Place' | 'Event' | 'Topic' | 'Object' | 'Emotion';
  name: string;
  attributes?: Record<string, any>;
}

interface GraphNode {
  id: string;
  type: 'memory' | 'entity' | 'cluster' | 'temporal';
  label: string;
  data: Memory | Entity | any;
  position?: { x: number; y: number };
  cluster?: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
}

interface ViewMode {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  layoutConfig: any;
}

const VIEW_MODES: ViewMode[] = [
  {
    id: 'overview',
    name: 'Overview',
    icon: Network,
    description: 'High-level view of your knowledge graph',
    layoutConfig: {
      name: 'fcose',
      quality: 'proof',
      randomize: false,
      animate: true,
      animationDuration: 1000,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 0.45,
      nestingFactor: 0.1,
      gravity: 0.25,
      numIter: 2500,
      tile: true,
      tilingPaddingVertical: 10,
      tilingPaddingHorizontal: 10,
    }
  },
  {
    id: 'temporal',
    name: 'Timeline',
    icon: Clock,
    description: 'Chronological view of memories and events',
    layoutConfig: {
      name: 'grid',
      rows: 10,
      cols: 20,
      position: (node: any) => {
        const date = new Date(node.data('created_at') || Date.now());
        const daysSinceEpoch = Math.floor(date.getTime() / (1000 * 60 * 60 * 24));
        return {
          row: Math.floor(Math.random() * 10),
          col: daysSinceEpoch % 20
        };
      }
    }
  },
  {
    id: 'semantic',
    name: 'Semantic',
    icon: Brain,
    description: 'Memories clustered by meaning and topics',
    layoutConfig: {
      name: 'cola',
      animate: true,
      maxSimulationTime: 4000,
      ungrabifyWhileSimulating: true,
      fit: true,
      padding: 30,
      nodeSpacing: 50,
      edgeLength: 150,
      randomize: false
    }
  },
  {
    id: 'entities',
    name: 'Entities',
    icon: Layers,
    description: 'Focus on people, places, and things',
    layoutConfig: {
      name: 'concentric',
      animate: true,
      animationDuration: 1000,
      levelWidth: () => 2,
      concentric: (node: any) => {
        if (node.data('nodeType') === 'entity') return 3;
        if (node.data('nodeType') === 'memory') return 1;
        return 2;
      }
    }
  }
];

const ENTITY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'Person': User,
  'Place': MapPin,
  'Event': Calendar,
  'Topic': Hash,
  'Object': Package,
  'Emotion': Heart
};

const ENTITY_COLORS: Record<string, string> = {
  'Person': '#3B82F6',      // Blue
  'Place': '#10B981',       // Green
  'Event': '#F59E0B',       // Amber
  'Topic': '#8B5CF6',       // Purple
  'Object': '#EF4444',      // Red
  'Emotion': '#EC4899',     // Pink
  'memory': '#6B7280',      // Gray
  'cluster': '#1F2937'      // Dark Gray
};

interface AdvancedKnowledgeGraphProps {
  onMemorySelect?: (memoryId: string) => void;
}

function AdvancedKnowledgeGraphInner({ onMemorySelect }: AdvancedKnowledgeGraphProps) {
  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialized, setIsInitialized] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>(VIEW_MODES[0]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [graphStats, setGraphStats] = useState({
    nodes: 0,
    edges: 0,
    entities: 0,
    memories: 0
  });
  const [zoomLevel, setZoomLevel] = useState(1);
  const [error, setError] = useState<string | null>(null);
  
  const userId = useSelector((state: RootState) => state.profile.userId);

  // Initialize Cytoscape
  useEffect(() => {
    const initGraph = async () => {
      if (!cyRef.current || isInitialized) return;
      
      try {
        const cytoscapeLib = await initializeCytoscape();
        if (!cytoscapeLib) return;

        cyInstance.current = cytoscapeLib({
      container: cyRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: any) => ENTITY_COLORS[ele.data('nodeType')] || '#6B7280',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '12px',
            'color': '#ffffff',
            'text-outline-width': 2,
            'text-outline-color': (ele: any) => ENTITY_COLORS[ele.data('nodeType')] || '#6B7280',
            'width': (ele: any) => {
              const type = ele.data('nodeType');
              if (type === 'cluster') return 80;
              if (type === 'entity') return 50;
              return 30;
            },
            'height': (ele: any) => {
              const type = ele.data('nodeType');
              if (type === 'cluster') return 80;
              if (type === 'entity') return 50;
              return 30;
            },
            'overlay-padding': 6,
            'z-index': 10
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#ffffff',
            'background-color': (ele: any) => ENTITY_COLORS[ele.data('nodeType')] || '#6B7280',
            'width': (ele: any) => {
              const type = ele.data('nodeType');
              if (type === 'cluster') return 90;
              if (type === 'entity') return 60;
              return 40;
            },
            'height': (ele: any) => {
              const type = ele.data('nodeType');
              if (type === 'cluster') return 90;
              if (type === 'entity') return 60;
              return 40;
            },
            'z-index': 999
          }
        },
        {
          selector: 'edge',
          style: {
            'width': (ele: any) => Math.max(1, ele.data('weight') || 1),
            'line-color': '#4B5563',
            'target-arrow-color': '#4B5563',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.6,
            'z-index': 5
          }
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#3B82F6',
            'target-arrow-color': '#3B82F6',
            'opacity': 1,
            'width': 3,
            'z-index': 999
          }
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#FBBF24',
            'line-color': '#FBBF24',
            'target-arrow-color': '#FBBF24',
            'transition-property': 'background-color, line-color, target-arrow-color',
            'transition-duration': '0.3s'
          }
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.25,
            'z-index': 1
          }
        }
      ],
      layout: viewMode.layoutConfig,
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2
    });

    // Event handlers
    cyInstance.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.data());
      
      // Highlight connected nodes
      cyInstance.current?.elements().removeClass('highlighted faded');
      node.addClass('highlighted');
      node.neighborhood().addClass('highlighted');
      cyInstance.current?.elements().not(node.neighborhood().union(node)).addClass('faded');
      
      if (node.data('nodeType') === 'memory' && onMemorySelect) {
        onMemorySelect(node.data('id'));
      }
    });

    cyInstance.current.on('tap', (evt) => {
      if (evt.target === cyInstance.current) {
        cyInstance.current?.elements().removeClass('highlighted faded');
        setSelectedNode(null);
      }
    });

        cyInstance.current.on('zoom', () => {
          setZoomLevel(cyInstance.current?.zoom() || 1);
        });

        setIsInitialized(true);
        setError(null);
      } catch (err) {
        console.error('Failed to initialize Cytoscape:', err);
        setError('Failed to initialize graph visualization');
      }
    };

    initGraph();

    return () => {
      if (cyInstance.current) {
        cyInstance.current.destroy();
        cyInstance.current = null;
      }
    };
  }, [onMemorySelect]);

  // Fetch and process graph data
  const loadGraphData = useCallback(async () => {
    if (!userId || !isInitialized || !cyInstance.current) return;
    
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get('/api/v1/memories/life-graph-data', {
        params: {
          limit: 500,
          include_entities: true,
          include_temporal_clusters: viewMode.id === 'temporal',
          focus_query: searchQuery || undefined
        }
      });

      const { nodes, edges, metadata } = response.data;
      
      // Convert to Cytoscape format
      const cyNodes = nodes.map((node: any) => ({
        data: {
          id: node.id,
          label: node.title || node.content?.substring(0, 50) || node.name || 'Unknown',
          nodeType: node.type,
          created_at: node.created_at,
          ...node
        },
        position: node.position
      }));

      const cyEdges = edges.map((edge: any, index: number) => ({
        data: {
          id: edge.id || `edge_${index}`,
          source: edge.source,
          target: edge.target,
          edgeType: edge.type,
          weight: edge.weight || 1
        }
      }));

      // Update graph
      cyInstance.current?.elements().remove();
      cyInstance.current?.add([...cyNodes, ...cyEdges]);
      
      // Apply layout
      cyInstance.current?.layout(viewMode.layoutConfig).run();
      
      // Update stats
      setGraphStats({
        nodes: nodes.length,
        edges: edges.length,
        entities: nodes.filter((n: any) => n.type !== 'memory').length,
        memories: nodes.filter((n: any) => n.type === 'memory').length
      });

    } catch (error) {
      console.error('Failed to load graph data:', error);
      setError('Failed to load graph data. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [userId, viewMode, searchQuery, isInitialized]);

  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  // Search functionality
  const handleSearch = useCallback(() => {
    if (!searchQuery) {
      cyInstance.current?.elements().removeClass('highlighted faded');
      return;
    }

    const matches = cyInstance.current?.nodes().filter((node) => {
      const label = node.data('label').toLowerCase();
      const content = node.data('content')?.toLowerCase() || '';
      return label.includes(searchQuery.toLowerCase()) || 
             content.includes(searchQuery.toLowerCase());
    });

    cyInstance.current?.elements().addClass('faded');
    matches?.removeClass('faded').addClass('highlighted');
    matches?.neighborhood().removeClass('faded');
  }, [searchQuery]);

  // Filter by entity type
  const handleFilter = useCallback((type: string) => {
    setFilterType(type);
    
    if (type === 'all') {
      cyInstance.current?.elements().removeClass('faded');
    } else {
      cyInstance.current?.elements().addClass('faded');
      cyInstance.current?.nodes(`[nodeType = "${type}"]`).removeClass('faded');
      cyInstance.current?.nodes(`[nodeType = "${type}"]`).neighborhood().removeClass('faded');
    }
  }, []);

  // Zoom controls
  const handleZoom = useCallback((delta: number) => {
    const newZoom = Math.max(0.1, Math.min(3, zoomLevel + delta));
    cyInstance.current?.zoom(newZoom);
    cyInstance.current?.center();
  }, [zoomLevel]);

  const handleFit = useCallback(() => {
    cyInstance.current?.fit();
  }, []);

  return (
    <div className="relative w-full h-full bg-background">
      {/* Loading State */}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
          >
            <Card className="p-6">
              <div className="flex flex-col items-center gap-3">
                <RefreshCw className="w-8 h-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Loading your knowledge graph...</p>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error State */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
          >
            <Card className="p-6 max-w-md">
              <div className="flex flex-col items-center gap-3">
                <X className="w-8 h-8 text-destructive" />
                <p className="text-sm text-destructive text-center">{error}</p>
                <Button onClick={() => {
                  setError(null);
                  loadGraphData();
                }} size="sm">
                  Try Again
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Control Panel */}
      <div className="absolute top-4 left-4 z-40 flex flex-col gap-4 max-w-sm">
        {/* View Mode Selector */}
        <Card className="bg-card/90 backdrop-blur-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">View Mode</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            {VIEW_MODES.map((mode) => {
              const Icon = mode.icon;
              return (
                <Button
                  key={mode.id}
                  variant={viewMode.id === mode.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode(mode)}
                  className="justify-start"
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {mode.name}
                </Button>
              );
            })}
          </CardContent>
        </Card>

        {/* Search */}
        <Card className="bg-card/90 backdrop-blur-sm">
          <CardContent className="pt-4">
            <div className="flex gap-2">
              <Input
                placeholder="Search memories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="flex-1"
              />
              <Button size="icon" onClick={handleSearch}>
                <Search className="w-4 h-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Entity Filter */}
        <Card className="bg-card/90 backdrop-blur-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Filter by Type</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Badge 
              variant={filterType === 'all' ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => handleFilter('all')}
            >
              All
            </Badge>
            {Object.entries(ENTITY_ICONS).map(([type, Icon]) => (
              <Badge
                key={type}
                variant={filterType === type ? 'default' : 'outline'}
                className="cursor-pointer flex items-center gap-1"
                onClick={() => handleFilter(type)}
              >
                <Icon className="w-3 h-3" />
                {type}
              </Badge>
            ))}
          </CardContent>
        </Card>

        {/* Graph Stats */}
        <Card className="bg-card/90 backdrop-blur-sm">
          <CardContent className="pt-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total Nodes:</span>
              <span className="font-medium">{graphStats.nodes}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Memories:</span>
              <span className="font-medium">{graphStats.memories}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Entities:</span>
              <span className="font-medium">{graphStats.entities}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Connections:</span>
              <span className="font-medium">{graphStats.edges}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Zoom Controls */}
      <div className="absolute top-4 right-4 z-40 flex flex-col gap-2">
        <Button size="icon" variant="outline" onClick={() => handleZoom(0.2)}>
          <ZoomIn className="w-4 h-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={() => handleZoom(-0.2)}>
          <ZoomOut className="w-4 h-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={handleFit}>
          <Maximize2 className="w-4 h-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={loadGraphData}>
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Selected Node Details */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="absolute bottom-4 left-4 right-4 z-40 max-w-2xl mx-auto"
          >
            <Card className="bg-card/95 backdrop-blur-sm">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {selectedNode.nodeType && ENTITY_ICONS[selectedNode.nodeType] && (
                      <div 
                        className="p-2 rounded-full"
                        style={{ backgroundColor: ENTITY_COLORS[selectedNode.nodeType] }}
                      >
                        {React.createElement(ENTITY_ICONS[selectedNode.nodeType], { 
                          className: "w-4 h-4 text-white" 
                        })}
                      </div>
                    )}
                    <div>
                      <CardTitle className="text-lg">{selectedNode.label}</CardTitle>
                      <CardDescription>
                        {selectedNode.nodeType} • {selectedNode.created_at ? 
                          new Date(selectedNode.created_at).toLocaleDateString() : 
                          'No date'
                        }
                      </CardDescription>
                    </div>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => setSelectedNode(null)}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {selectedNode.content && (
                  <p className="text-sm text-muted-foreground mb-3">
                    {selectedNode.content}
                  </p>
                )}
                {selectedNode.attributes && (
                  <div className="space-y-1 text-sm">
                    {Object.entries(selectedNode.attributes).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="text-muted-foreground capitalize">{key}:</span>
                        <span>{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {selectedNode.nodeType === 'memory' && (
                  <Button 
                    size="sm" 
                    className="mt-3"
                    onClick={() => {
                      // Navigate to memory details page
                      window.location.href = `/memory/${selectedNode.id}`;
                    }}
                  >
                    View Memory Details
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Graph Container */}
      <div ref={cyRef} className="w-full h-full" />

      {/* Help Button */}
      <Button
        size="icon"
        variant="outline"
        className="absolute bottom-4 right-4 z-40"
        onClick={() => {
          // TODO: Show help dialog
        }}
      >
        <Info className="w-4 h-4" />
      </Button>
    </div>
  );
}

// Client-side only wrapper to prevent SSR issues
export default function AdvancedKnowledgeGraph(props: AdvancedKnowledgeGraphProps) {
  const [isClient, setIsClient] = useState(false);
  
  useEffect(() => {
    setIsClient(true);
  }, []);
  
  if (!isClient) {
    return (
      <div className="relative w-full h-full bg-background flex items-center justify-center">
        <Card className="p-6">
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Initializing graph...</p>
          </div>
        </Card>
      </div>
    );
  }
  
  return <AdvancedKnowledgeGraphInner {...props} />;
}