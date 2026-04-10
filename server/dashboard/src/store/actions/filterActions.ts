export type FilterType = "events" | "memories";

export interface FilterParameter {
  key: string;
  values: string[];
}

export enum FilterConstants {
  FETCH_FILTERS = "FETCH_FILTERS",
  SET_FILTERS = "SET_FILTERS",
  SET_LOADING = "SET_LOADING",
  SET_ERROR = "SET_ERROR",
}

export type FilterActions =
  | { type: FilterConstants.FETCH_FILTERS; payload: { filterType: FilterType } }
  | { type: FilterConstants.SET_FILTERS; payload: { filterType: FilterType; parameters: FilterParameter[] } }
  | { type: FilterConstants.SET_LOADING; payload: { filterType: FilterType; isLoading: boolean } }
  | { type: FilterConstants.SET_ERROR; payload: { filterType: FilterType; error: string | null } };

export interface FilterSliceState {
  parameters: FilterParameter[];
  isLoading: boolean;
  error: string | null;
}

export interface FilterState {
  events: FilterSliceState;
  memories: FilterSliceState;
}

export const setFilters = (filterType: FilterType, parameters: FilterParameter[]): FilterActions => ({
  type: FilterConstants.SET_FILTERS,
  payload: { filterType, parameters },
});

export const setFiltersLoading = (filterType: FilterType, isLoading: boolean): FilterActions => ({
  type: FilterConstants.SET_LOADING,
  payload: { filterType, isLoading },
});

export const setFiltersError = (filterType: FilterType, error: string | null): FilterActions => ({
  type: FilterConstants.SET_ERROR,
  payload: { filterType, error },
});
