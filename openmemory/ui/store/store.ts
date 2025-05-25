import { configureStore } from '@reduxjs/toolkit';
import memoriesReducer from './memoriesSlice';
import profileReducer from './profileSlice';
import appsReducer from './appsSlice';
import uiReducer from './uiSlice';
import filtersReducer from './filtersSlice';
import configReducer from './configSlice';

export const store = configureStore({
  reducer: {
    memories: memoriesReducer,
    profile: profileReducer,
    apps: appsReducer,
    ui: uiReducer,
    filters: filtersReducer,
    config: configReducer,
  },
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
// Inferred type: {memories: MemoriesState, profile: ProfileState, apps: AppsState, ui: UIState, ...}
export type AppDispatch = typeof store.dispatch; 