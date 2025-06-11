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
    
    // For local development with USER_ID environment variable
    const localUserId = process.env.NEXT_PUBLIC_USER_ID;
    if (localUserId) {
      console.log('API Client: Local development detected, using local token');
      // In local development, we'll use our special local token
      config.headers.Authorization = `Bearer local-dev-token`;
    } else if (token) {
      // Normal flow for production
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

export default apiClient; 