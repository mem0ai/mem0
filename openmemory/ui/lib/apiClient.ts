import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';
import { getGlobalAccessToken } from '../contexts/AuthContext'; // Import the accessor

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

// Function to get the access token - this would typically be from your AuthContext
// For now, we assume you will pass it or have a way to access it globally.
// In a real app, you'd integrate this with useAuth() from AuthContext.

// Interceptor to add the auth token to requests
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getGlobalAccessToken(); 
    console.log('API Client Interceptor: Token being used:', token); // DEBUG LINE
    console.log('API Client Interceptor: Request URL:', config.url); // DEBUG LINE

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

export default apiClient; 