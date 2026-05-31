import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface DialogState {
  updateMemory: {
    isOpen: boolean;
    memoryId: string | null;
    memoryContent: string | null;
  };
}

interface UIState {
  dialogs: DialogState;
}

const initialState: UIState = {
  dialogs: {
    updateMemory: {
      isOpen: false,
      memoryId: null,
      memoryContent: null,
    },
  },
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    openUpdateMemoryDialog: (state, action: PayloadAction<{ memoryId: string; memoryContent: string }>) => {
      state.dialogs.updateMemory.isOpen = true;
      state.dialogs.updateMemory.memoryId = action.payload.memoryId;
      state.dialogs.updateMemory.memoryContent = action.payload.memoryContent;
    },
    closeUpdateMemoryDialog: (state) => {
      state.dialogs.updateMemory.isOpen = false;
      state.dialogs.updateMemory.memoryId = null;
      state.dialogs.updateMemory.memoryContent = null;
    },
  },
});

export const {
  openUpdateMemoryDialog,
  closeUpdateMemoryDialog,
} = uiSlice.actions;

export default uiSlice.reducer; 