import { Stats, StatsConstants, StatsActions } from "../actions/statsAction";

interface StatsState {
  stats: Stats;
  isLoading: boolean;
  error: string | null;
}

const initialState: StatsState = {
  stats: {
    memory_count: 0,
    team_size: 0,
    active_api_keys: 0,
  },
  isLoading: false,
  error: null,
};

export const statsReducer = (state: StatsState = initialState, action: StatsActions): StatsState => {
  switch (action.type) {
    case StatsConstants.SET_STATS:
      return { ...state, stats: action.payload, isLoading: false, error: null };
    default:
      return state;
  }
};
