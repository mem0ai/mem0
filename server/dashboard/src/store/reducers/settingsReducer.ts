interface SettingsState {
  isSettingsVisible: boolean;
}

const initialState: SettingsState = {
  isSettingsVisible: false,
};

export const settingsReducer = (state: SettingsState = initialState, action: any): SettingsState => {
  switch (action.type) {
    case "TOGGLE_SETTINGS":
      return { ...state, isSettingsVisible: !state.isSettingsVisible };
    default:
      return state;
  }
};
