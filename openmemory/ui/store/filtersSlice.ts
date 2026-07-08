import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface Category {
  id: string;
  name: string;
  description: string;
  updated_at: string;
  created_at: string;
}

export interface FiltersState {
  apps: {
    selectedApps: string[];
    selectedCategories: string[];
    sortColumn: string;
    sortDirection: 'asc' | 'desc';
    showArchived: boolean;
  };
  categories: {
    items: Category[];
    total: number;
    isLoading: boolean;
    error: string | null;
  };
}

const initialState: FiltersState = {
  apps: {
    selectedApps: [],
    selectedCategories: [],
    sortColumn: 'created_at',
    sortDirection: 'desc',
    showArchived: false,
  },
  categories: {
    items: [],
    total: 0,
    isLoading: false,
    error: null
  }
};

const filtersSlice = createSlice({
  name: 'filters',
  initialState,
  reducers: {
    setCategoriesLoading: (state) => {
      state.categories.isLoading = true;
      state.categories.error = null;
    },
    setCategoriesSuccess: (state, action: PayloadAction<{ categories: Category[]; total: number }>) => {
      state.categories.items = action.payload.categories;
      state.categories.total = action.payload.total;
      state.categories.isLoading = false;
      state.categories.error = null;
    },
    setCategoriesError: (state, action: PayloadAction<string>) => {
      state.categories.isLoading = false;
      state.categories.error = action.payload;
    },
    setSelectedApps: (state, action: PayloadAction<string[]>) => {
      state.apps.selectedApps = action.payload;
    },
    setSelectedCategories: (state, action: PayloadAction<string[]>) => {
      state.apps.selectedCategories = action.payload;
    },
    setShowArchived: (state, action: PayloadAction<boolean>) => {
      state.apps.showArchived = action.payload;
    },
    clearFilters: (state) => {
      state.apps.selectedApps = [];
      state.apps.selectedCategories = [];
      state.apps.showArchived = false;
    },
    setSortingState: (state, action: PayloadAction<{ column: string; direction: 'asc' | 'desc' }>) => {
      state.apps.sortColumn = action.payload.column;
      state.apps.sortDirection = action.payload.direction;
    },
  },
});

export const {
  setCategoriesLoading,
  setCategoriesSuccess,
  setCategoriesError,
  setSelectedApps,
  setSelectedCategories,
  setShowArchived,
  clearFilters,
  setSortingState
} = filtersSlice.actions;

export default filtersSlice.reducer; 