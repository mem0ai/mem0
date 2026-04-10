import { api } from '@/utils/api';
import { MEMORY_ENDPOINTS } from '@/utils/api-endpoints';

export const useMemory = () => {
  const updateMemory = async (memoryId: string, updatedText: string) => {
    const response = await api.put(MEMORY_ENDPOINTS.BY_ID(memoryId), { text: updatedText });
    if (response.data.ok) {
      return response.data;
    }
    throw new Error('Failed to update memory');
  };

  return { updateMemory };
};
