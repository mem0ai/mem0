interface MemoryState {
  memories: any[];
  isLoading: boolean;
  error: string | null;
  currentMemory: any | null;
}

const initialState: MemoryState = {
  memories: [],
  isLoading: false,
  error: null,
  currentMemory: null,
};

export const memoryReducer = (state: MemoryState = initialState, action: any): MemoryState => {
  switch (action.type) {
    case "SET_MEMORIES":
      return { ...state, memories: action.payload, isLoading: false, error: null };
    case "SET_CURRENT_MEMORY":
      return { ...state, currentMemory: action.payload };
    case "SET_MEMORIES_LOADING":
      return { ...state, isLoading: true, error: null };
    case "SET_MEMORIES_ERROR":
      return { ...state, isLoading: false, error: action.payload };
    default:
      return state;
  }
};
