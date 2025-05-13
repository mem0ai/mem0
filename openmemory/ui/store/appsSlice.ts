import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface AppMemory {
  id: string;
  user_id: string;
  content: string;
  state: string;
  updated_at: string;
  deleted_at: string | null;
  app_id: string;
  vector: any;
  metadata_: Record<string, any>;
  created_at: string;
  archived_at: string | null;
  categories: string[];
  app_name: string;
}

export interface AccessedMemory {
  memory: AppMemory;
  access_count: number;
}

export interface AppDetails {
  is_active: boolean;
  total_memories_created: number;
  total_memories_accessed: number;
  first_accessed: string | null;
  last_accessed: string | null;
}

export interface App {
  id: string;
  name: string;
  total_memories_created: number;
  total_memories_accessed: number;
  is_active?: boolean;
}

interface MemoriesState {
  items: AppMemory[];
  total: number;
  page: number;
  loading: boolean;
  error: string | null;
}

interface AccessedMemoriesState {
  items: AccessedMemory[];
  total: number;
  page: number;
  loading: boolean;
  error: string | null;
}

interface AppsState {
  apps: App[];
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
  filters: {
    searchQuery: string;
    isActive: 'all' | true | false;
    sortBy: 'name' | 'memories' | 'memories_accessed';
    sortDirection: 'asc' | 'desc';
  };
  selectedApp: {
    details: AppDetails | null;
    memories: {
      created: MemoriesState;
      accessed: AccessedMemoriesState;
    };
    loading: boolean;
    error: string | null;
  };
}

const initialMemoriesState: MemoriesState = {
  items: [],
  total: 0,
  page: 1,
  loading: false,
  error: null,
};

const initialAccessedMemoriesState: AccessedMemoriesState = {
  items: [],
  total: 0,
  page: 1,
  loading: false,
  error: null,
};

const initialState: AppsState = {
  apps: [],
  status: 'idle',
  error: null,
  filters: {
    searchQuery: '',
    isActive: 'all',
    sortBy: 'name',
    sortDirection: 'asc'
  },
  selectedApp: {
    details: null,
    memories: {
      created: initialMemoriesState,
      accessed: initialAccessedMemoriesState,
    },
    loading: false,
    error: null,
  },
};

const appsSlice = createSlice({
  name: 'apps',
  initialState,
  reducers: {
    setAppsLoading: (state) => {
      state.status = 'loading';
      state.error = null;
    },
    setAppsSuccess: (state, action: PayloadAction<App[]>) => {
      state.status = 'succeeded';
      state.apps = action.payload;
      state.error = null;
    },
    setAppsError: (state, action: PayloadAction<string>) => {
      state.status = 'failed';
      state.error = action.payload;
    },
    resetAppsState: (state) => {
      state.status = 'idle';
      state.error = null;
      state.apps = [];
      state.selectedApp = initialState.selectedApp;
    },
    setSelectedAppLoading: (state) => {
      state.selectedApp.loading = true;
    },
    setSelectedAppDetails: (state, action: PayloadAction<AppDetails>) => {
      state.selectedApp.details = action.payload;
      state.selectedApp.loading = false;
      state.selectedApp.error = null;
    },
    setSelectedAppError: (state, action: PayloadAction<string>) => {
      state.selectedApp.loading = false;
      state.selectedApp.error = action.payload;
    },
    setCreatedMemoriesLoading: (state) => {
      state.selectedApp.memories.created.loading = true;
      state.selectedApp.memories.created.error = null;
    },
    setCreatedMemoriesSuccess: (state, action: PayloadAction<{ items: AppMemory[]; total: number; page: number }>) => {
      state.selectedApp.memories.created.items = action.payload.items;
      state.selectedApp.memories.created.total = action.payload.total;
      state.selectedApp.memories.created.page = action.payload.page;
      state.selectedApp.memories.created.loading = false;
      state.selectedApp.memories.created.error = null;
    },
    setCreatedMemoriesError: (state, action: PayloadAction<string>) => {
      state.selectedApp.memories.created.loading = false;
      state.selectedApp.memories.created.error = action.payload;
    },
    setAccessedMemoriesLoading: (state) => {
      state.selectedApp.memories.accessed.loading = true;
      state.selectedApp.memories.accessed.error = null;
    },
    setAccessedMemoriesSuccess: (state, action: PayloadAction<{ items: AccessedMemory[]; total: number; page: number }>) => {
      state.selectedApp.memories.accessed.items = action.payload.items;
      state.selectedApp.memories.accessed.total = action.payload.total;
      state.selectedApp.memories.accessed.page = action.payload.page;
      state.selectedApp.memories.accessed.loading = false;
      state.selectedApp.memories.accessed.error = null;
    },
    setAccessedMemoriesError: (state, action: PayloadAction<string>) => {
      state.selectedApp.memories.accessed.loading = false;
      state.selectedApp.memories.accessed.error = action.payload;
    },
    setAppDetails: (state, action: PayloadAction<{ appId: string; isActive: boolean }>) => {
      const app = state.apps.find(app => app.id === action.payload.appId);
      if (app) {
        app.is_active = action.payload.isActive;
      }
      if (state.selectedApp.details) {
        state.selectedApp.details.is_active = action.payload.isActive;
      }
    },
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.filters.searchQuery = action.payload;
    },
    setActiveFilter: (state, action: PayloadAction<'all' | true | false>) => {
      state.filters.isActive = action.payload;
    },
    setSortBy: (state, action: PayloadAction<'name' | 'memories' | 'memories_accessed'>) => {
      state.filters.sortBy = action.payload;
    },
    setSortDirection: (state, action: PayloadAction<'asc' | 'desc'>) => {
      state.filters.sortDirection = action.payload;
    },
  },
});

export const {
  setAppsLoading,
  setAppsSuccess,
  setAppsError,
  resetAppsState,
  setSelectedAppLoading,
  setSelectedAppDetails,
  setSelectedAppError,
  setCreatedMemoriesLoading,
  setCreatedMemoriesSuccess,
  setCreatedMemoriesError,
  setAccessedMemoriesLoading,
  setAccessedMemoriesSuccess,
  setAccessedMemoriesError,
  setAppDetails,
  setSearchQuery,
  setActiveFilter,
  setSortBy,
  setSortDirection,
} = appsSlice.actions;

export default appsSlice.reducer;