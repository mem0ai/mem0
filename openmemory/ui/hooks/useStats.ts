import { useState, useCallback } from 'react';
// import axios from 'axios'; // REMOVE
import apiClient from '../lib/apiClient'; // ADD
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '@/store/store';
import { setApps, setTotalApps } from '@/store/profileSlice';
import { setTotalMemories } from '@/store/profileSlice';

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
interface APIStatsResponse {
  total_memories: number;
  total_apps: number;
  apps: any[];
}


interface UseStatsReturn {
  fetchStats: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export const useStats = (): UseStatsReturn => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const dispatch = useDispatch<AppDispatch>();
  const user_id = useSelector((state: RootState) => state.profile.userId); // Keep for now if backend endpoint specifically needs it

  // const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765"; // No longer needed

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Your backend /api/v1/stats endpoint seems to expect user_id as a query param from the logs.
      const response = await apiClient.get<APIStatsResponse>(
        `/api/v1/stats`, { params: { user_id: user_id } }
      );
      dispatch(setTotalMemories(response.data.total_memories));
      dispatch(setTotalApps(response.data.total_apps));
      dispatch(setApps(response.data.apps));
      setIsLoading(false); // Set loading false on success
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to fetch stats';
      setError(errorMessage);
      setIsLoading(false);
      throw new Error(errorMessage);
    }
  }, [dispatch, user_id]);

  return { fetchStats, isLoading, error };
};