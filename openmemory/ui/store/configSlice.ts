import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface LLMConfig {
  model: string;
  temperature: number;
  max_tokens: number;
  api_key?: string;
  ollama_base_url?: string;
}

export interface LLMProvider {
  provider: string;
  config: LLMConfig;
}

export interface EmbedderConfig {
  model: string;
  api_key?: string;
  ollama_base_url?: string;
}

export interface EmbedderProvider {
  provider: string;
  config: EmbedderConfig;
}

export interface Mem0Config {
  llm?: LLMProvider;
  embedder?: EmbedderProvider;
}

export interface OpenMemoryConfig {
  custom_instructions?: string | null;
}

export interface ConfigState {
  openmemory: OpenMemoryConfig;
  mem0: Mem0Config;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: ConfigState = {
  openmemory: {
    custom_instructions: null,
  },
  mem0: {
    llm: {
      provider: 'openai',
      config: {
        model: 'gpt-4o-mini',
        temperature: 0.1,
        max_tokens: 2000,
        api_key: 'env:OPENAI_API_KEY',
      },
    },
    embedder: {
      provider: 'openai',
      config: {
        model: 'text-embedding-3-small',
        api_key: 'env:OPENAI_API_KEY',
      },
    },
  },
  status: 'idle',
  error: null,
};

const configSlice = createSlice({
  name: 'config',
  initialState,
  reducers: {
    setConfigLoading: (state) => {
      state.status = 'loading';
      state.error = null;
    },
    setConfigSuccess: (state, action: PayloadAction<{ openmemory?: OpenMemoryConfig; mem0: Mem0Config }>) => {
      if (action.payload.openmemory) {
        state.openmemory = action.payload.openmemory;
      }
      state.mem0 = action.payload.mem0;
      state.status = 'succeeded';
      state.error = null;
    },
    setConfigError: (state, action: PayloadAction<string>) => {
      state.status = 'failed';
      state.error = action.payload;
    },
    updateOpenMemory: (state, action: PayloadAction<OpenMemoryConfig>) => {
      state.openmemory = action.payload;
    },
    updateLLM: (state, action: PayloadAction<LLMProvider>) => {
      state.mem0.llm = action.payload;
    },
    updateEmbedder: (state, action: PayloadAction<EmbedderProvider>) => {
      state.mem0.embedder = action.payload;
    },
    updateMem0Config: (state, action: PayloadAction<Mem0Config>) => {
      state.mem0 = action.payload;
    },
  },
});

export const {
  setConfigLoading,
  setConfigSuccess,
  setConfigError,
  updateOpenMemory,
  updateLLM,
  updateEmbedder,
  updateMem0Config,
} = configSlice.actions;

export default configSlice.reducer; 