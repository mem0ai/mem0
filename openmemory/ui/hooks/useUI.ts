import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '@/store/store';
import { openUpdateMemoryDialog, closeUpdateMemoryDialog } from '@/store/uiSlice';

export const useUI = () => {
  const dispatch = useDispatch<AppDispatch>();
  const updateMemoryDialog = useSelector((state: RootState) => state.ui.dialogs.updateMemory);

  const handleOpenUpdateMemoryDialog = (memoryId: string, memoryContent: string) => {
    dispatch(openUpdateMemoryDialog({ memoryId, memoryContent }));
  };

  const handleCloseUpdateMemoryDialog = () => {
    dispatch(closeUpdateMemoryDialog());
  };

  return {
    updateMemoryDialog,
    handleOpenUpdateMemoryDialog,
    handleCloseUpdateMemoryDialog,
  };
}; 