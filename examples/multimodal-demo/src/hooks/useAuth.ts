import { useState, useEffect } from 'react';
import { Provider } from '@/constants/messages';

interface UseAuthReturn {
  mem0ApiKey: string;
  openaiApiKey: string;
  provider: Provider;
  user: string;
  setAuth: (mem0: string, openai: string, provider: Provider) => void;
  setUser: (user: string) => void;
  clearAuth: () => void;
  clearUser: () => void;
}

export const useAuth = (): UseAuthReturn => {
  const [mem0ApiKey, setMem0ApiKey] = useState<string>('');
  const [openaiApiKey, setOpenaiApiKey] = useState<string>('');
  const [provider, setProvider] = useState<Provider>('openai');
  const [user, setUser] = useState<string>('');

  useEffect(() => {
    const mem0 = localStorage.getItem('mem0ApiKey');
    const openai = localStorage.getItem('openaiApiKey');
    const savedProvider = localStorage.getItem('provider') as Provider;
    const savedUser = localStorage.getItem('user');

    if (mem0 && openai && savedProvider) {
      setAuth(mem0, openai, savedProvider);
    }
    if (savedUser) {
      setUser(savedUser);
    }
  }, []);

  const setAuth = (mem0: string, openai: string, provider: Provider) => {
    setMem0ApiKey(mem0);
    setOpenaiApiKey(openai);
    setProvider(provider);
    localStorage.setItem('mem0ApiKey', mem0);
    localStorage.setItem('openaiApiKey', openai);
    localStorage.setItem('provider', provider);
  };

  const clearAuth = () => {
    localStorage.removeItem('mem0ApiKey');
    localStorage.removeItem('openaiApiKey');
    localStorage.removeItem('provider');
    setMem0ApiKey('');
    setOpenaiApiKey('');
    setProvider('openai');
  };

  const updateUser = (user: string) => {
    setUser(user);
    localStorage.setItem('user', user);
  };

  const clearUser = () => {
    localStorage.removeItem('user');
    setUser('');
  };

  return {
    mem0ApiKey,
    openaiApiKey,
    provider,
    user,
    setAuth,
    setUser: updateUser,
    clearAuth,
    clearUser,
  };
}; 