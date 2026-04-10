import axios, { AxiosInstance } from 'axios';

let cachedToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  cachedToken = token;
};

export const getAccessToken = (): string | null => {
  return cachedToken;
};

const handleTokenError = () => {
  cachedToken = null;
};

const createApi = (): AxiosInstance & { postStream: (url: string, data: any) => Promise<Response> } => {
  const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL,
  });

  // Request interceptor
  api.interceptors.request.use(
    async (config) => {
      if (cachedToken) {
        config.headers.Authorization = `Bearer ${cachedToken}`;
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor
  api.interceptors.response.use(
    (response) => {
      try {
        if (typeof response.data === 'object' && response.data !== null) {
          response.data.ok = true;
        }
      } catch (e) {
        return response;
      }
      return response;
    },
    async (error) => {
      if (error.response?.status === 401) {
        handleTokenError();
        // Try to refresh the token
        try {
          const refreshResponse = await fetch('/api/auth/refresh', {
            method: 'POST',
            credentials: 'include',
          });
          if (refreshResponse.ok) {
            const data = await refreshResponse.json();
            setAccessToken(data.access_token);
            // Retry the original request
            error.config.headers.Authorization = `Bearer ${data.access_token}`;
            return api.request(error.config);
          }
        } catch {
          // Refresh failed — redirect to login
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }
      }
      if (error.response?.data?.error) {
        return Promise.reject(error.response.data.error);
      }
      return Promise.reject(error);
    }
  );

  // Streaming POST using fetch
  const postStream = async (url: string, data: any): Promise<Response> => {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: cachedToken ? `Bearer ${cachedToken}` : '',
      },
      body: JSON.stringify(data),
    });

    if (response.status === 401) {
      handleTokenError();
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Request failed');
    }

    return response;
  };

  return Object.assign(api, { postStream });
};

export const api = createApi();
