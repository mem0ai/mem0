import { useCallback, useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

export interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

export interface GraphRelationship {
  id: string;
  type: string;
  source: string;
  target: string;
  properties: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

export interface GraphStats {
  node_count: number;
  relationship_count: number;
  node_types: Array<{ label: string; count: number }>;
}

export function useGraphApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);

  const fetchGraphData = useCallback(async (userId?: string, limit: number = 100) => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { limit };
      if (userId) params.user_id = userId;

      const response = await axios.get<GraphData>(`${API_URL}/api/v1/graph/data`, { params });
      setGraphData(response.data);
      return response.data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || "Failed to fetch graph data";
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGraphStats = useCallback(async (userId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {};
      if (userId) params.user_id = userId;

      const response = await axios.get<GraphStats>(`${API_URL}/api/v1/graph/stats`, { params });
      setStats(response.data);
      return response.data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || "Failed to fetch graph stats";
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const searchGraph = useCallback(async (query: string, userId?: string, limit: number = 50) => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { query, limit };
      if (userId) params.user_id = userId;

      const response = await axios.get<GraphData>(`${API_URL}/api/v1/graph/search`, { params });
      setGraphData(response.data);
      return response.data;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || "Failed to search graph";
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    graphData,
    stats,
    fetchGraphData,
    fetchGraphStats,
    searchGraph,
  };
}
