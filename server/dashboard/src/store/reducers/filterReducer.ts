import { FilterConstants, FilterState, FilterActions } from "../actions/filterActions";

const initialState: FilterState = {
  events: { parameters: [], isLoading: false, error: null },
  memories: { parameters: [], isLoading: false, error: null },
};

export const filterReducer = (state: FilterState = initialState, action: FilterActions): FilterState => {
  switch (action.type) {
    case FilterConstants.FETCH_FILTERS:
      return {
        ...state,
        [action.payload.filterType]: { ...state[action.payload.filterType], isLoading: true, error: null },
      };
    case FilterConstants.SET_FILTERS:
      return {
        ...state,
        [action.payload.filterType]: { ...state[action.payload.filterType], parameters: action.payload.parameters, isLoading: false, error: null },
      };
    case FilterConstants.SET_LOADING:
      return {
        ...state,
        [action.payload.filterType]: { ...state[action.payload.filterType], isLoading: action.payload.isLoading },
      };
    case FilterConstants.SET_ERROR:
      return {
        ...state,
        [action.payload.filterType]: { ...state[action.payload.filterType], isLoading: false, error: action.payload.error },
      };
    default:
      return state;
  }
};
