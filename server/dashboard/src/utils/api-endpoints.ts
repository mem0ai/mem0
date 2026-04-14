export const AUTH_ENDPOINTS = {
  SETUP_STATUS: "/auth/setup-status",
  REGISTER: "/auth/register",
  LOGIN: "/auth/login",
  REFRESH: "/auth/refresh",
  ME: "/auth/me",
} as const;

export const MEMORY_ENDPOINTS = {
  BASE: "/memories",
  BY_ID: (memoryId: string) => `/memories/${memoryId}`,
  HISTORY: (memoryId: string) => `/memories/${memoryId}/history`,
  SEARCH: "/search",
  CONFIGURE: "/configure",
  RESET: "/reset",
} as const;

export const API_KEY_ENDPOINTS = {
  BASE: "/api-keys",
  BY_ID: (keyId: string) => `/api-keys/${keyId}`,
} as const;

export const REQUEST_ENDPOINTS = {
  BASE: "/requests",
} as const;

export const ENTITY_ENDPOINTS = {
  BASE: "/entities",
  BY_ID: (type: string, id: string) =>
    `/entities/${type}/${encodeURIComponent(id)}`,
} as const;
