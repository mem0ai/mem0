import { useState, useCallback } from 'react';
import apiClient from '../lib/apiClient';
import { Memory, Client, Category } from '@/components/types';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '@/store/store';
import { setAccessLogs, setMemoriesSuccess, setSelectedMemory, setRelatedMemories } from '@/store/memoriesSlice';
import { usePostHog } from 'posthog-js/react';

// Define the new simplified memory type
export interface SimpleMemory {
  id: string;
  text: string;
  created_at: string;
  state: string;
  categories: string[];
  app_name: string;
}

// Define the shape of the API response item
interface ApiMemoryItem {
  id: string;
  content: string;
  created_at: string;
  state: string;
  app_id: string;
  categories: string[];
  metadata_?: Record<string, any>;
  app_name: string;
}

// Define the shape of the API response
interface ApiResponse {
  items: ApiMemoryItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

interface AccessLogEntry {
  id: string;
  app_name: string;
  accessed_at: string;
}

interface AccessLogResponse {
  total: number;
  page: number;
  page_size: number;
  logs: AccessLogEntry[];
}

interface RelatedMemoryItem {
  id: string;
  content: string;
  created_at: number;
  state: string;
  app_id: string;
  app_name: string;
  categories: string[];
  metadata_: Record<string, any>;
}

interface RelatedMemoriesResponse {
  items: RelatedMemoryItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

interface UseMemoriesApiReturn {
  fetchMemories: (
    query?: string,
    page?: number,
    size?: number,
    filters?: {
      apps?: string[];
      categories?: string[];
      sortColumn?: string;
      sortDirection?: 'asc' | 'desc';
      showArchived?: boolean;
    }
  ) => Promise<{ memories: Memory[]; total: number; pages: number }>;
  fetchMemoryById: (memoryId: string) => Promise<void>;
  fetchAccessLogs: (memoryId: string, page?: number, pageSize?: number) => Promise<void>;
  fetchRelatedMemories: (memoryId: string) => Promise<void>;
  createMemory: (text: string) => Promise<void>;
  deleteMemories: (memoryIds: string[]) => Promise<void>;
  updateMemory: (memoryId: string, content: string) => Promise<void>;
  updateMemoryState: (memoryIds: string[], state: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
  hasUpdates: number;
  memories: Memory[];
  selectedMemory: SimpleMemory | null;
}

export const useMemoriesApi = (): UseMemoriesApiReturn => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasUpdates, setHasUpdates] = useState<number>(0);
  const dispatch = useDispatch<AppDispatch>();
  const user_id = useSelector((state: RootState) => state.profile.userId);
  const memories = useSelector((state: RootState) => state.memories.memories);
  const selectedMemory = useSelector((state: RootState) => state.memories.selectedMemory);
  const posthog = usePostHog();

  const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

  const fetchMemories = useCallback(async (
    query?: string,
    page: number = 1,
    size: number = 10,
    filters?: {
      apps?: string[];
      categories?: string[];
      sortColumn?: string;
      sortDirection?: 'asc' | 'desc';
      showArchived?: boolean;
    }
  ): Promise<{ memories: Memory[], total: number, pages: number }> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping fetchMemories.");
      return { memories: [], total: 0, pages: 0 };
    }
    setIsLoading(true);
    setError(null);
    try {
      // Use the working GET endpoint instead of the failing POST filter endpoint
      const params: any = {
        page: page,
        size: size,
      };

      if (query) params.search_query = query;
      if (filters?.apps && filters.apps.length > 0) params.app_id = filters.apps[0]; // GET endpoint takes single app_id
      if (filters?.categories && filters.categories.length > 0) params.categories = filters.categories.join(',');
      if (filters?.sortColumn) params.sort_column = filters.sortColumn.toLowerCase();
      if (filters?.sortDirection) params.sort_direction = filters.sortDirection;

      const response = await apiClient.get<ApiResponse>(
        `/api/v1/memories/`,
        { params }
      );

      const adaptedMemories: Memory[] = response.data.items.map((item: ApiMemoryItem) => ({
        id: item.id,
        memory: item.content,
        created_at: new Date(item.created_at).getTime(),
        state: item.state as "active" | "paused" | "archived" | "deleted",
        metadata: item.metadata_,
        categories: item.categories as Category[],
        client: 'api',
        app_name: item.app_name
      }));
      setIsLoading(false);
      dispatch(setMemoriesSuccess(adaptedMemories));
      return {
        memories: adaptedMemories,
        total: response.data.total,
        pages: response.data.pages
      };
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch memories';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  }, [user_id, dispatch]);

  const createMemory = async (text: string): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping createMemory.");
      setError("User not authenticated to create memory.");
      throw new Error("User not authenticated to create memory.");
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const memoryData = {
        user_id: user_id,
        text: text,
        infer: false,
        app_name: "jean memory",
      }
      console.log("Creating memory with data:", memoryData);
      const response = await apiClient.post<ApiMemoryItem>(`/api/v1/memories/`, memoryData);
      
      // 📊 Track memory creation with PostHog
      if (posthog) {
        posthog.capture('memory_created', {
          memory_length: text.length,
          app_name: 'jean memory',
          memory_id: response.data?.id || 'unknown'
        });
      }
      
      setIsLoading(false);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to create memory';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const deleteMemories = async (memory_ids: string[]) => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping deleteMemories.");
      return;
    }
    try {
      await apiClient.delete(`/api/v1/memories/`, {
        data: { memory_ids, user_id }
      });
      dispatch(setMemoriesSuccess(memories.filter((memory: Memory) => !memory_ids.includes(memory.id))));
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to delete memories';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const fetchMemoryById = async (memoryId: string): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping fetchMemoryById.");
      return;
    }
    if (memoryId === "") {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<any>(
        `/api/v1/memories/${memoryId}`
      );
      setIsLoading(false);
      // Map the API response to SimpleMemory format
      const memoryData: SimpleMemory = {
        id: response.data.id,
        text: response.data.content,  // Map content to text
        created_at: response.data.created_at,
        state: response.data.state,
        categories: response.data.categories,
        app_name: response.data.app_name
      };
      dispatch(setSelectedMemory(memoryData));
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch memory';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const fetchAccessLogs = async (memoryId: string, page: number = 1, pageSize: number = 10): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping fetchAccessLogs.");
      return;
    }
    if (memoryId === "") {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<AccessLogResponse>(
        `/api/v1/memories/${memoryId}/access-log`, { params: { page, page_size: pageSize } }
      );
      setIsLoading(false);
      dispatch(setAccessLogs(response.data.logs));
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch access logs';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const fetchRelatedMemories = async (memoryId: string): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping fetchRelatedMemories.");
      return;
    }
    if (memoryId === "") {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<RelatedMemoriesResponse>(
        `/api/v1/memories/${memoryId}/related`
      );

      const adaptedMemories: Memory[] = response.data.items.map((item: RelatedMemoryItem) => ({
        id: item.id,
        memory: item.content,
        created_at: item.created_at,
        state: item.state as "active" | "paused" | "archived" | "deleted",
        metadata: item.metadata_,
        categories: item.categories as Category[],
        client: 'api',
        app_name: item.app_name
      }));

      setIsLoading(false);
      dispatch(setRelatedMemories(adaptedMemories));
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch related memories';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const updateMemory = async (memoryId: string, content: string): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping updateMemory.");
      return;
    }
    if (memoryId === "") {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.put(`/api/v1/memories/${memoryId}`, {
        memory_id: memoryId,
        memory_content: content,
        user_id: user_id
      });
      setIsLoading(false);
      setHasUpdates(hasUpdates + 1);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to update memory';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  const updateMemoryState = async (memoryIds: string[], state: string): Promise<void> => {
    if (!user_id) {
      console.log("useMemoriesApi: No user_id, skipping updateMemoryState.");
      return;
    }
    if (memoryIds.length === 0) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.post(`/api/v1/memories/actions/pause`, {
        memory_ids: memoryIds,
        all_for_app: true,
        state: state,
        user_id: user_id
      });
      dispatch(setMemoriesSuccess(memories.map((memory: Memory) => {
        if (memoryIds.includes(memory.id)) {
          return { ...memory, state: state as "active" | "paused" | "archived" | "deleted" };
        }
        return memory;
      })));

      // If archive, delete the memory
      if (state === "archived") {
        dispatch(setMemoriesSuccess(memories.filter((memory: Memory) => !memoryIds.includes(memory.id))));
      }

      // if selected memory, update it
      if (selectedMemory?.id && memoryIds.includes(selectedMemory.id)) {
        dispatch(setSelectedMemory({ ...selectedMemory, state: state as "active" | "paused" | "archived" | "deleted" }));
      }

      setIsLoading(false);
      setHasUpdates(hasUpdates + 1);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to update memory state';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  };

  return {
    fetchMemories,
    fetchMemoryById,
    fetchAccessLogs,
    fetchRelatedMemories,
    createMemory,
    deleteMemories,
    updateMemory,
    updateMemoryState,
    isLoading,
    error,
    hasUpdates,
    memories,
    selectedMemory
  };
};