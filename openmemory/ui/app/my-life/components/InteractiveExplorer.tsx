"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { 
  ChevronLeft, 
  ChevronRight, 
  Home, 
  Loader2, 
  Search, 
  Sparkles,
  MoreHorizontal,
  Brain,
  Heart,
  Briefcase,
  Users,
  MapPin,
  Target,
  Trophy
} from "lucide-react";
import apiClient from "@/lib/apiClient";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useExplorerCache } from "@/hooks/useExplorerCache";

interface ExplorerNode {
  id: string;
  title: string;
  description?: string;
  query?: string;
  level: number;
  type: 'cluster' | 'memory' | 'topic';
  memory_count?: number;
  can_expand?: boolean;
  content?: string;
  score?: number;
  source?: string;
  parent_node?: string;
  metadata?: any;
  icon?: React.ComponentType<{ className?: string }>;
}

interface ExplorationPath {
  node: ExplorerNode;
  timestamp: number;
}

interface Suggestion {
  title: string;
  description: string;
  query: string;
  type: string;
}

interface InteractiveExplorerProps {
  onMemorySelect: (memoryId: string | null) => void;
}

const INITIAL_CLUSTERS = [
  { 
    id: 'personal', 
    title: 'Personal Life', 
    description: 'Relationships, family, and personal experiences',
    query: 'personal relationships family friends',
    icon: Heart,
    color: 'hsl(0, 70%, 60%)'
  },
  { 
    id: 'work', 
    title: 'Work & Career', 
    description: 'Professional development and work experiences',
    query: 'work career professional development',
    icon: Briefcase,
    color: 'hsl(240, 70%, 60%)'
  },
  { 
    id: 'learning', 
    title: 'Learning & Growth', 
    description: 'Education, skills, and knowledge acquisition',
    query: 'learning education skills knowledge',
    icon: Brain,
    color: 'hsl(150, 60%, 50%)'
  },
  { 
    id: 'interests', 
    title: 'Hobbies & Interests', 
    description: 'Creative activities and personal interests',
    query: 'hobbies interests creative activities',
    icon: Sparkles,
    color: 'hsl(45, 80%, 60%)'
  },
  { 
    id: 'experiences', 
    title: 'Life Experiences', 
    description: 'Travel, places, and memorable moments',
    query: 'travel places locations experiences',
    icon: MapPin,
    color: 'hsl(200, 80%, 60%)'
  },
  { 
    id: 'goals', 
    title: 'Goals & Aspirations', 
    description: 'Future plans and personal objectives',
    query: 'goals aspirations future plans',
    icon: Target,
    color: 'hsl(280, 60%, 60%)'
  },
  { 
    id: 'achievements', 
    title: 'Achievements', 
    description: 'Accomplishments and milestones',
    query: 'achievements accomplishments milestones',
    icon: Trophy,
    color: 'hsl(30, 80%, 60%)'
  },
  { 
    id: 'connections', 
    title: 'Social Network', 
    description: 'People, communities, and relationships',
    query: 'people colleagues community network',
    icon: Users,
    color: 'hsl(180, 60%, 60%)'
  }
];

export default function InteractiveExplorer({ onMemorySelect }: InteractiveExplorerProps) {
  const [currentLevel, setCurrentLevel] = useState(0);
  const [explorationPath, setExplorationPath] = useState<ExplorationPath[]>([]);
  const [currentNodes, setCurrentNodes] = useState<ExplorerNode[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [expandedMemories, setExpandedMemories] = useState<Set<string>>(new Set());
  
  const user_id = useSelector((state: RootState) => state.profile.userId);
  const expansionCache = useExplorerCache<any>({ ttl: 15 * 60 * 1000 }); // 15 minute cache
  const suggestionCache = useExplorerCache<Suggestion[]>({ ttl: 30 * 60 * 1000 }); // 30 minute cache

  // Initialize with top-level clusters
  useEffect(() => {
    const initialNodes: ExplorerNode[] = INITIAL_CLUSTERS.map(cluster => ({
      id: cluster.id,
      title: cluster.title,
      description: cluster.description,
      query: cluster.query,
      level: 1,
      type: 'cluster',
      can_expand: true,
      icon: cluster.icon,
      metadata: { color: cluster.color }
    }));
    setCurrentNodes(initialNodes);
  }, []);

  const expandNode = async (node: ExplorerNode) => {
    if (!user_id) {
      console.log("No user_id available for expansion");
      return;
    }

    setIsExpanding(true);
    
    try {
      console.log("Expanding node:", node);
      
      // Check cache first
      const cacheKey = `expand_${node.id}_${node.query || node.title}`;
      const cachedData = expansionCache.get(cacheKey);
      
      let expansionData;
      if (cachedData) {
        console.log("Using cached expansion data for:", node.id);
        expansionData = cachedData;
      } else {
        console.log("Fetching new expansion data for:", node.id);
        
        // Call expansion API
        const response = await apiClient.post('/api/v1/memories/life-graph-expand', {
          focal_node_id: node.id,
          query: node.query || node.title,
          depth: 1,
          strategy: 'NODE_HYBRID_SEARCH_NODE_DISTANCE',
          limit: 15
        });

        expansionData = response.data;
        
        // Cache the result
        expansionCache.set(cacheKey, expansionData);
      }
      
      // Add current node to exploration path
      const newPath = [...explorationPath, { node, timestamp: Date.now() }];
      setExplorationPath(newPath);
      setCurrentLevel(currentLevel + 1);

      console.log("Expansion response:", expansionData);

      // Convert API response to explorer nodes
      const expandedNodes: ExplorerNode[] = [];
      
      if (expansionData.nodes) {
        expansionData.nodes.forEach((apiNode: any, index: number) => {
          const explorerNode: ExplorerNode = {
            id: apiNode.id || `expanded_${index}`,
            title: apiNode.content ? 
              (apiNode.content.length > 60 ? `${apiNode.content.substring(0, 60)}...` : apiNode.content) :
              `Memory ${index + 1}`,
            description: apiNode.content || '',
            level: currentLevel + 1,
            type: 'memory',
            can_expand: false,
            content: apiNode.content,
            score: apiNode.score,
            source: apiNode.source,
            parent_node: node.id,
            metadata: apiNode.metadata || {}
          };
          expandedNodes.push(explorerNode);
        });
      }

      // If no memories found, create a fallback node
      if (expandedNodes.length === 0) {
        expandedNodes.push({
          id: `no_results_${node.id}`,
          title: "No memories found",
          description: "Try exploring a different area or check back later as more memories are added.",
          level: currentLevel + 1,
          type: 'topic',
          can_expand: false
        });
      }

      setCurrentNodes(expandedNodes);

      // Get AI suggestions for next exploration
      generateSuggestions(newPath, node);

    } catch (error) {
      console.error("Expansion failed:", error);
      // Create error node
      setCurrentNodes([{
        id: `error_${node.id}`,
        title: "Exploration temporarily unavailable",
        description: "Please try again in a moment.",
        level: currentLevel + 1,
        type: 'topic',
        can_expand: false
      }]);
    } finally {
      setIsExpanding(false);
    }
  };

  const generateSuggestions = async (path: ExplorationPath[], currentNode: ExplorerNode) => {
    try {
      // Check cache first
      const cacheKey = `suggest_${currentNode.id}_${path.length}`;
      const cachedSuggestions = suggestionCache.get(cacheKey);
      
      if (cachedSuggestions) {
        console.log("Using cached suggestions for:", currentNode.id);
        setSuggestions(cachedSuggestions);
        setShowSuggestions(true);
        return;
      }
      
      console.log("Generating new suggestions for:", currentNode.id);
      const response = await apiClient.post('/api/v1/memories/life-graph-suggest', {
        current_path: path.map(p => p.node.title),
        current_node: currentNode.title,
        context: currentNode.description || ''
      });

      const suggestions = response.data.suggestions || [];
      
      // Cache the suggestions
      suggestionCache.set(cacheKey, suggestions);
      
      setSuggestions(suggestions);
      setShowSuggestions(true);
    } catch (error) {
      console.error("Suggestion generation failed:", error);
      setSuggestions([]);
    }
  };

  const navigateBack = () => {
    if (explorationPath.length === 0) return;

    if (explorationPath.length === 1) {
      // Return to initial clusters
      const initialNodes: ExplorerNode[] = INITIAL_CLUSTERS.map(cluster => ({
        id: cluster.id,
        title: cluster.title,
        description: cluster.description,
        query: cluster.query,
        level: 1,
        type: 'cluster',
        can_expand: true,
        icon: cluster.icon,
        metadata: { color: cluster.color }
      }));
      setCurrentNodes(initialNodes);
      setExplorationPath([]);
      setCurrentLevel(0);
    } else {
      // Navigate to previous level
      const newPath = explorationPath.slice(0, -1);
      setExplorationPath(newPath);
      setCurrentLevel(currentLevel - 1);
      
      // Re-expand the previous node
      const previousNode = newPath[newPath.length - 1]?.node;
      if (previousNode) {
        expandNode(previousNode);
      }
    }
    
    setShowSuggestions(false);
  };

  const goHome = () => {
    const initialNodes: ExplorerNode[] = INITIAL_CLUSTERS.map(cluster => ({
      id: cluster.id,
      title: cluster.title,
      description: cluster.description,
      query: cluster.query,
      level: 1,
      type: 'cluster',
      can_expand: true,
      icon: cluster.icon,
      metadata: { color: cluster.color }
    }));
    setCurrentNodes(initialNodes);
    setExplorationPath([]);
    setCurrentLevel(0);
    setShowSuggestions(false);
  };

  const exploreFromSuggestion = async (suggestion: Suggestion) => {
    setIsExpanding(true);
    setShowSuggestions(false);
    
    try {
      const response = await apiClient.post('/api/v1/memories/life-graph-expand', {
        focal_node_id: `suggestion_${Date.now()}`,
        query: suggestion.query,
        depth: 1,
        limit: 15
      });

      const expansionData = response.data;
      
      // Create suggestion node and add to path
      const suggestionNode: ExplorerNode = {
        id: `suggestion_${Date.now()}`,
        title: suggestion.title,
        description: suggestion.description,
        query: suggestion.query,
        level: currentLevel + 1,
        type: 'topic',
        can_expand: true
      };

      const newPath = [...explorationPath, { node: suggestionNode, timestamp: Date.now() }];
      setExplorationPath(newPath);
      setCurrentLevel(currentLevel + 1);

      // Convert results to explorer nodes
      const expandedNodes: ExplorerNode[] = [];
      
      if (expansionData.nodes) {
        expansionData.nodes.forEach((apiNode: any, index: number) => {
          expandedNodes.push({
            id: apiNode.id || `suggestion_result_${index}`,
            title: apiNode.content ? 
              (apiNode.content.length > 60 ? `${apiNode.content.substring(0, 60)}...` : apiNode.content) :
              `Memory ${index + 1}`,
            description: apiNode.content || '',
            level: currentLevel + 2,
            type: 'memory',
            can_expand: false,
            content: apiNode.content,
            score: apiNode.score,
            source: apiNode.source,
            metadata: apiNode.metadata || {}
          });
        });
      }

      setCurrentNodes(expandedNodes);

    } catch (error) {
      console.error("Suggestion exploration failed:", error);
    } finally {
      setIsExpanding(false);
    }
  };

  const toggleMemoryExpansion = (memoryId: string) => {
    const newExpanded = new Set(expandedMemories);
    if (newExpanded.has(memoryId)) {
      newExpanded.delete(memoryId);
    } else {
      newExpanded.add(memoryId);
    }
    setExpandedMemories(newExpanded);
  };

  const handleMemoryClick = (node: ExplorerNode) => {
    if (node.type === 'memory') {
      onMemorySelect(node.id);
      toggleMemoryExpansion(node.id);
    }
  };

  // Breadcrumb component
  const Breadcrumbs = () => (
    <div className="flex items-center gap-2 mb-6 flex-wrap">
      <Button
        variant="ghost"
        size="sm"
        onClick={goHome}
        className="text-primary hover:text-primary/80"
      >
        <Home className="h-4 w-4 mr-1" />
        My Life
      </Button>
      
      {explorationPath.map((pathItem, index) => (
        <div key={pathItem.timestamp} className="flex items-center gap-2">
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {pathItem.node.title}
          </span>
        </div>
      ))}
      
      {explorationPath.length > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={navigateBack}
          className="ml-auto"
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
      )}
    </div>
  );

  return (
    <div className="w-full h-full p-6 overflow-auto bg-background">
      <Breadcrumbs />
      
      {/* Loading State */}
      {(isLoading || isExpanding) && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-muted-foreground">
              {isExpanding ? "Exploring memories..." : "Loading..."}
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      {!isLoading && !isExpanding && (
        <AnimatePresence mode="wait">
          <motion.div
            key={currentLevel}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {currentNodes.map((node) => {
              const IconComponent = node.icon;
              const isExpanded = expandedMemories.has(node.id);
              
              return (
                <motion.div
                  key={node.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card 
                    className={`cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-105 ${
                      node.type === 'memory' ? 'border-primary/20' : ''
                    }`}
                    onClick={() => {
                      if (node.can_expand) {
                        expandNode(node);
                      } else if (node.type === 'memory') {
                        handleMemoryClick(node);
                      }
                    }}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          {IconComponent && (
                            <IconComponent 
                              className="h-5 w-5 text-primary" 
                              style={{ color: node.metadata?.color }}
                            />
                          )}
                          <CardTitle className="text-sm font-medium leading-tight">
                            {node.title}
                          </CardTitle>
                        </div>
                        {node.can_expand && (
                          <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        )}
                      </div>
                      
                      {node.memory_count && (
                        <Badge variant="secondary" className="w-fit text-xs">
                          {node.memory_count} memories
                        </Badge>
                      )}
                    </CardHeader>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>
        </AnimatePresence>
      )}

      {/* AI Suggestions Panel */}
      <AnimatePresence>
        {showSuggestions && suggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="mt-8 p-4 bg-muted/50 rounded-lg border border-border"
          >
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="h-5 w-5 text-primary" />
              <h3 className="font-medium">Suggested Explorations</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {suggestions.map((suggestion, index) => (
                <Card 
                  key={index}
                  className="cursor-pointer hover:bg-accent/50 transition-colors"
                  onClick={() => exploreFromSuggestion(suggestion)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Search className="h-4 w-4 text-primary" />
                      <h4 className="font-medium text-sm">{suggestion.title}</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {suggestion.description}
                    </p>
                    <Badge variant="outline" className="mt-2 text-xs">
                      {suggestion.type}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!isLoading && !isExpanding && currentNodes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Brain className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No memories found</h3>
          <p className="text-muted-foreground mb-4">
            Try exploring a different area or add more memories to your collection.
          </p>
          <Button onClick={goHome} variant="outline">
            <Home className="h-4 w-4 mr-2" />
            Return to Overview
          </Button>
        </div>
      )}
    </div>
  );
}