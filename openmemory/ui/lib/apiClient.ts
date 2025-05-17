import axios, { InternalAxiosRequestConfig, AxiosError } from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

// Function to get the access token - this would typically be from your AuthContext
// For now, we assume you will pass it or have a way to access it globally.
// In a real app, you'd integrate this with useAuth() from AuthContext.

// Interceptor to add the auth token to requests
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // How you get the token depends on your auth state management.
    // If using the AuthContext.tsx we defined earlier, you can't directly call useAuth() here
    // as this is not a React component/hook. 
    // A common pattern is to have a separate function in AuthContext to get the token,
    // or to retrieve it from localStorage if Supabase stores it there predictably.
    
    // For Supabase, the session object (which contains the access_token) is managed by its client.
    // Let's try to get it directly from the supabase client, assuming it's initialized.
    // This is a simplified approach for this interceptor.
    // A more robust way might involve a singleton or a service that can access the AuthContext state.

    let token: string | null = null;
    try {
      // This is a common way Supabase stores session for client-side access
      const sessionKey = `sb-${new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).hostname.replace(/\./g, '-')}-auth-token`;
      const sessionDataString = localStorage.getItem(sessionKey);
      if (sessionDataString) {
        const sessionData = JSON.parse(sessionDataString);
        token = sessionData.access_token;
      }
    } catch (e) {
      console.error('Error retrieving token for API client', e);
    }

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