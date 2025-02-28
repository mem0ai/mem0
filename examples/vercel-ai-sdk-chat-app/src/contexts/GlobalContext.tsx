/* eslint-disable @typescript-eslint/no-explicit-any */
import { createContext } from 'react';
import { Message, Memory, FileInfo } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { useChat } from '@/hooks/useChat';
import { useFileHandler } from '@/hooks/useFileHandler';
import { Provider } from '@/constants/messages';

interface GlobalContextType {
  selectedUser: string;
  selectUserHandler: (user: string) => void;
  clearUserHandler: () => void;
  messages: Message[];
  memories: Memory[];
  handleSend: (content: string) => Promise<void>;
  thinking: boolean;
  selectedMem0Key: string;
  selectedOpenAIKey: string;
  selectedProvider: Provider;
  selectorHandler: (mem0: string, openai: string, provider: Provider) => void;
  clearConfiguration: () => void;
  selectedFile: FileInfo | null;
  setSelectedFile: (file: FileInfo | null) => void;
  file: File | null;
  setFile: (file: File | null) => void;
}

const GlobalContext = createContext<GlobalContextType>({} as GlobalContextType);

const GlobalState = (props: { children: React.ReactNode }) => {
  const {
    mem0ApiKey: selectedMem0Key,
    openaiApiKey: selectedOpenAIKey,
    provider: selectedProvider,
    user: selectedUser,
    setAuth: selectorHandler,
    setUser: selectUserHandler,
    clearAuth: clearConfiguration,
    clearUser: clearUserHandler,
  } = useAuth();

  const {
    selectedFile,
    file,
    fileData,
    setSelectedFile,
    handleFile,
    clearFile,
  } = useFileHandler();

  const {
    messages,
    memories,
    thinking,
    sendMessage,
  } = useChat({
    user: selectedUser,
    mem0ApiKey: selectedMem0Key,
    openaiApiKey: selectedOpenAIKey,
    provider: selectedProvider,
  });

  const handleSend = async (content: string) => {
    if (file) {
      await sendMessage(content, {
        type: file.type,
        data: fileData!,
      });
      clearFile();
    } else {
      await sendMessage(content);
    }
  };

  const setFile = async (newFile: File | null) => {
    if (newFile) {
      await handleFile(newFile);
    } else {
      clearFile();
    }
  };

  return (
    <GlobalContext.Provider
      value={{
        selectedUser,
        selectUserHandler,
        clearUserHandler,
        messages,
        memories,
        handleSend,
        thinking,
        selectedMem0Key,
        selectedOpenAIKey,
        selectedProvider,
        selectorHandler,
        clearConfiguration,
        selectedFile,
        setSelectedFile,
        file,
        setFile,
      }}
    >
      {props.children}
    </GlobalContext.Provider>
  );
};

export default GlobalContext;
export { GlobalState };