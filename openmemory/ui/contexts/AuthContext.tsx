import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { Session, User, AuthError, AuthChangeEvent } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';

interface AuthContextType {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  error: AuthError | null;
  signInWithPassword: typeof supabase.auth.signInWithPassword;
  signUpWithPassword: typeof supabase.auth.signUp;
  signInWithGoogle: () => Promise<void>;
  signOut: typeof supabase.auth.signOut;
  accessToken: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AuthError | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    supabase.auth.getSession().then(({ data: { session: currentSession } }: { data: { session: Session | null }}) => {
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      setAccessToken(currentSession?.access_token ?? null);
      setIsLoading(false);
    });

    const { data: authListener } = supabase.auth.onAuthStateChange(
      (event: AuthChangeEvent, currentSession: Session | null) => {
        setSession(currentSession);
        setUser(currentSession?.user ?? null);
        setAccessToken(currentSession?.access_token ?? null);
        setIsLoading(false);
        setError(null); // Clear previous errors on auth state change
      }
    );

    return () => {
      authListener?.unsubscribe();
    };
  }, []);

  const signInWithPassword = async (
    credentials: Parameters<typeof supabase.auth.signInWithPassword>[0]
  ) => {
    setIsLoading(true);
    setError(null);
    const { data, error } = await supabase.auth.signInWithPassword(credentials);
    if (error) setError(error);
    // Session state will be updated by onAuthStateChange listener
    setIsLoading(false);
    return { data, error };
  };

  const signUpWithPassword = async (
    credentials: Parameters<typeof supabase.auth.signUp>[0]
  ) => {
    setIsLoading(true);
    setError(null);
    const { data, error } = await supabase.auth.signUp(credentials);
    if (error) setError(error);
    setIsLoading(false);
    return { data, error };
  };

  const signInWithGoogle = async () => {
    setIsLoading(true);
    setError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        // Optional: Add redirectTo if needed for specific post-OAuth flows
        // redirectTo: `${window.location.origin}/auth/callback` 
      },
    });
    if (error) {
      setError(error);
      setIsLoading(false);
    }
    // Supabase handles the redirect and onAuthStateChange will update session
  };

  const signOut = async () => {
    setIsLoading(true);
    setError(null);
    const { error } = await supabase.auth.signOut();
    if (error) setError(error);
    // Session state will be updated by onAuthStateChange listener
    setIsLoading(false);
    return { error };
  };

  const value = {
    session,
    user,
    isLoading,
    error,
    signInWithPassword,
    signUpWithPassword,
    signInWithGoogle,
    signOut,
    accessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 