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
    console.log('API Client Interceptor: Token being used:', token ? 'Token present' : 'No token'); // DEBUG LINE
    console.log('API Client Interceptor: Request URL:', config.url); // DEBUG LINE
    
    if (token) {
      // Always use the real Supabase token (local or production)
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.warn('API Client: No authentication token available');
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

export default apiClient; 