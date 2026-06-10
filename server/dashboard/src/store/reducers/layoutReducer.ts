enum LayoutActionConstants {
  TOGGLE_SIDEBAR = "TOGGLE_SIDEBAR",
}

interface LayoutState {
  isSidebarCollapsed: boolean;
}

const initialState: LayoutState = {
  isSidebarCollapsed: false,
};

export const layoutReducer = (
  state: LayoutState = initialState,
  action: { type: string },
): LayoutState => {
  switch (action.type) {
    case LayoutActionConstants.TOGGLE_SIDEBAR:
      return { ...state, isSidebarCollapsed: !state.isSidebarCollapsed };
    default:
      return state;
  }
};

export const toggleSidebar = () => ({
  type: LayoutActionConstants.TOGGLE_SIDEBAR as const,
});
