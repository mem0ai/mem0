enum LayoutActionConstants {
  TOGGLE_SIDEBAR = "TOGGLE_SIDEBAR",
  CLOSE_SIDEBAR = "CLOSE_SIDEBAR",
}

interface State {
  isSidebarCollapsed: boolean;
}

type Action =
  | { type: LayoutActionConstants.TOGGLE_SIDEBAR }
  | { type: LayoutActionConstants.CLOSE_SIDEBAR };

const initialState: State = {
  isSidebarCollapsed: false,
};

export const layoutReducer = (state: State = initialState, action: Action): State => {
  switch (action.type) {
    case LayoutActionConstants.TOGGLE_SIDEBAR:
      return { ...state, isSidebarCollapsed: !state.isSidebarCollapsed };
    case LayoutActionConstants.CLOSE_SIDEBAR:
      return { ...state, isSidebarCollapsed: true };
    default:
      return state;
  }
};

export const toggleSidebar = () => ({ type: LayoutActionConstants.TOGGLE_SIDEBAR as const });
export const closeSidebar = () => ({ type: LayoutActionConstants.CLOSE_SIDEBAR as const });
