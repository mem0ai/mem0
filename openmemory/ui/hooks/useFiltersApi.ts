import { useState, useCallback } from 'react';
import apiClient from '../lib/apiClient';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '@/store/store';
import {
  Category,
  setCategoriesLoading,
  setCategoriesSuccess,
  setCategoriesError,
  setSortingState,
  setSelectedApps,
  setSelectedCategories
} from '@/store/filtersSlice';

interface CategoriesResponse {
  categories: string[] | Category[];  // Backend returns string[], but we'll handle both
  total: number;
}

export interface UseFiltersApiReturn {
  fetchCategories: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
  updateApps: (apps: string[]) => void;
  updateCategories: (categories: string[]) => void;
  updateSort: (column: string, direction: 'asc' | 'desc') => void;
}

export const useFiltersApi = (): UseFiltersApiReturn => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const dispatch = useDispatch<AppDispatch>();
  const user_id = useSelector((state: RootState) => state.profile.userId);
  // const { accessToken } = useAuth(); // Alternative: Get token directly from AuthContext

  const fetchCategories = useCallback(async (): Promise<void> => {
    // if (!accessToken) { // Alternative check
    if (!user_id) { // Check if user_id (from Redux, now reflects Supabase auth state) is null
      console.log("useFiltersApi: No user_id, skipping fetchCategories.");
      // Optionally dispatch an action to clear categories or set an appropriate state
      // dispatch(setCategoriesSuccess({ categories: [], total: 0 }));
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    dispatch(setCategoriesLoading());
    setError(null); // Clear previous errors
    try {
      // The backend /api/v1/memories/categories seems to want user_id from your logs.
      // However, all routers are protected by get_current_supa_user, so backend already knows the user.
      // Ideally, the backend endpoint should use the JWT user. Sending user_id is okay if backend handles it.
      console.log(`useFiltersApi: Fetching categories for user_id (from redux): ${user_id}`); // DEBUG
      const response = await apiClient.get<CategoriesResponse>(
        `/api/v1/memories/categories`, { params: { user_id: user_id } } 
      );

      // Transform string array to Category objects if needed
      const categoriesData = Array.isArray(response.data.categories) 
        ? response.data.categories.map((cat, index) => {
            if (typeof cat === 'string') {
              // Backend returns string array, convert to Category objects
              return {
                id: `cat_${index}`,
                name: cat,
                description: '',
                updated_at: new Date().toISOString(),
                created_at: new Date().toISOString()
              };
            }
            // Already a Category object
            return cat;
          })
        : [];

      dispatch(setCategoriesSuccess({
        categories: categoriesData,
        total: response.data.total
      }));
      setIsLoading(false);
    } catch (err: any) {
      console.error("useFiltersApi: Failed to fetch categories", err); // DEBUG
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch categories';
      setError(errorMessage);
      dispatch(setCategoriesError(errorMessage));
      setIsLoading(false);
      // It's often better not to re-throw here unless the component specifically needs to catch it.
      // throw new Error(errorMessage); 
    }
  }, [dispatch, user_id]);

  const updateApps = useCallback((apps: string[]) => {
    dispatch(setSelectedApps(apps));
  }, [dispatch]);

  const updateCategories = useCallback((categories: string[]) => {
    dispatch(setSelectedCategories(categories));
  }, [dispatch]);

  const updateSort = useCallback((column: string, direction: 'asc' | 'desc') => {
    dispatch(setSortingState({ column, direction }));
  }, [dispatch]);

  return {
    fetchCategories,
    isLoading,
    error,
    updateApps,
    updateCategories,
    updateSort
  };
}; 