import { useState, useCallback } from 'react';
import axios from 'axios';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '@/store/store';
import {
  App,
  AppDetails,
  AppMemory,
  AccessedMemory,
  setAppsSuccess,
  setAppsError,
  setAppsLoading,
  setSelectedAppLoading,
  setSelectedAppDetails,
  setCreatedMemoriesLoading,
  setCreatedMemoriesSuccess,
  setCreatedMemoriesError,
  setAccessedMemoriesLoading,
  setAccessedMemoriesSuccess,
  setAccessedMemoriesError,
  setSelectedAppError,
} from '@/store/appsSlice';

interface ApiResponse {
  total: number;
  page: number;
  page_size: number;
  apps: App[];
}

interface MemoriesResponse {
  total: number;
  page: number;
  page_size: number;
  memories: AppMemory[];
}

interface AccessedMemoriesResponse {
  total: number;
  page: number;
  page_size: number;
  memories: AccessedMemory[];
}

interface FetchAppsParams {
  name?: string;
  is_active?: boolean;
  sort_by?: 'name' | 'memories' | 'memories_accessed';
  sort_direction?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

interface UseAppsApiReturn {
  fetchApps: (params?: FetchAppsParams) => Promise<{ apps: App[], total: number }>;
  fetchAppDetails: (appId: string) => Promise<void>;
  fetchAppMemories: (appId: string, page?: number, pageSize?: number) => Promise<void>;
  fetchAppAccessedMemories: (appId: string, page?: number, pageSize?: number) => Promise<void>;
  updateAppDetails: (appId: string, details: { is_active: boolean }) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export const useAppsApi = (): UseAppsApiReturn => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const dispatch = useDispatch<AppDispatch>();
  const user_id = useSelector((state: RootState) => state.profile.userId);

  const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

  const fetchApps = useCallback(async (params: FetchAppsParams = {}): Promise<{ apps: App[], total: number }> => {
    const {
      name,
      is_active,
      sort_by = 'name',
      sort_direction = 'asc',
      page = 1,
      page_size = 10
    } = params;

    setIsLoading(true);
    dispatch(setAppsLoading());
    try {
      const queryParams = new URLSearchParams({
        page: String(page),
        page_size: String(page_size)
      });

      if (name) queryParams.append('name', name);
      if (is_active !== undefined) queryParams.append('is_active', String(is_active));
      if (sort_by) queryParams.append('sort_by', sort_by);
      if (sort_direction) queryParams.append('sort_direction', sort_direction);

      const response = await axios.get<ApiResponse>(
        `${URL}/api/v1/apps/?${queryParams.toString()}`
      );

      setIsLoading(false);
      dispatch(setAppsSuccess(response.data.apps));
      return {
        apps: response.data.apps,
        total: response.data.total
      };
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch apps';
      setError(errorMessage);
      dispatch(setAppsError(errorMessage));
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  }, [dispatch]);

  const fetchAppDetails = useCallback(async (appId: string): Promise<void> => {
    setIsLoading(true);
    dispatch(setSelectedAppLoading());
    try {
      const response = await axios.get<AppDetails>(
        `${URL}/api/v1/apps/${appId}`
      );
      dispatch(setSelectedAppDetails(response.data));
      setIsLoading(false);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch app details';
      dispatch(setSelectedAppError(errorMessage));
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  }, [dispatch]);

  const fetchAppMemories = useCallback(async (appId: string, page: number = 1, pageSize: number = 10): Promise<void> => {
    setIsLoading(true);
    dispatch(setCreatedMemoriesLoading());
    try {
      const response = await axios.get<MemoriesResponse>(
        `${URL}/api/v1/apps/${appId}/memories?page=${page}&page_size=${pageSize}`
      );
      dispatch(setCreatedMemoriesSuccess({
        items: response.data.memories,
        total: response.data.total,
        page: response.data.page,
      }));
      setIsLoading(false);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch app memories';
      dispatch(setCreatedMemoriesError(errorMessage));
      setError(errorMessage);
      setIsLoading(false);
    }
  }, [dispatch]);

  const fetchAppAccessedMemories = useCallback(async (appId: string, page: number = 1, pageSize: number = 10): Promise<void> => {
    setIsLoading(true);
    dispatch(setAccessedMemoriesLoading());
    try {
      const response = await axios.get<AccessedMemoriesResponse>(
        `${URL}/api/v1/apps/${appId}/accessed?page=${page}&page_size=${pageSize}`
      );
      dispatch(setAccessedMemoriesSuccess({
        items: response.data.memories,
        total: response.data.total,
        page: response.data.page,
      }));
      setIsLoading(false);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch accessed memories';
      dispatch(setAccessedMemoriesError(errorMessage));
      setError(errorMessage);
      setIsLoading(false);
    }
  }, [dispatch]);

  const updateAppDetails = async (appId: string, details: { is_active: boolean }) => {
    setIsLoading(true);
    try {
      const response = await axios.put(
        `${URL}/api/v1/apps/${appId}?is_active=${details.is_active}`
      );
      setIsLoading(false);
      return response.data;
    } catch (error) {
      console.error("Failed to update app details:", error);
      setIsLoading(false);
      throw error;
    }
  };

  return {
    fetchApps,
    fetchAppDetails,
    fetchAppMemories,
    fetchAppAccessedMemories,
    updateAppDetails,
    isLoading,
    error
  };
};
