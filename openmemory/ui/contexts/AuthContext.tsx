"use client";

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import {
  Session, User, AuthError, AuthChangeEvent,
  AuthResponse, // For signIn and signUp
  SignInWithPasswordCredentials,
  SignUpWithPasswordCredentials
} from '@supabase/supabase-js'; // Added more specific types
import { supabase } from '../lib/supabaseClient';

// Store the latest token globally, accessible by non-React modules
let globalAccessToken: string | null = null;

export const getGlobalAccessToken = () => globalAccessToken;

interface AuthContextType {
  session: Session | null;
  user: User | null;
  isLoading: boolean;
  error: AuthError | null;
  // Simplified return types for our wrapper functions
  signInWithPassword: (credentials: SignInWithPasswordCredentials) => Promise<AuthResponse>; 
  signUpWithPassword: (credentials: SignUpWithPasswordCredentials) => Promise<AuthResponse>;
  signInWithGoogle: () => Promise<void>; // signInWithOAuth doesn't have a straightforward return to type here for data
  signOut: () => Promise<{ error: AuthError | null }>; // signOut returns { error }
  accessToken: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AuthError | null>(null);
  const [localAccessToken, setLocalAccessToken] = useState<string | null>(null); // State variable for token

  useEffect(() => {
    const updateTokenStates = (currentSession: Session | null) => {
      const token = currentSession?.access_token ?? null;
      setLocalAccessToken(token);
      globalAccessToken = token;
      console.log('AuthContext: globalAccessToken updated:', globalAccessToken); // DEBUG LINE
    };

    setIsLoading(true);
    supabase.auth.getSession().then(({ data: { session: currentSession } }) => { // Removed explicit typing, rely on inference
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      updateTokenStates(currentSession);
      setIsLoading(false);
    });

    const { data: authListener } = supabase.auth.onAuthStateChange(
      (event: AuthChangeEvent, currentSession: Session | null) => {
        setSession(currentSession);
        setUser(currentSession?.user ?? null);
        updateTokenStates(currentSession);
        setIsLoading(false);
        setError(null);
      }
    );

    return () => {
      authListener.subscription?.unsubscribe(); // Corrected unsubscribe path
    };
  }, []);

  const signInWithPassword = async (
    credentials: SignInWithPasswordCredentials
  ): Promise<AuthResponse> => {
    setIsLoading(true);
    setError(null);
    const response = await supabase.auth.signInWithPassword(credentials);
    if (response.error) setError(response.error);
    setIsLoading(false);
    return response;
  };

  const signUpWithPassword = async (
    credentials: SignUpWithPasswordCredentials
  ): Promise<AuthResponse> => {
    setIsLoading(true);
    setError(null);
    const response = await supabase.auth.signUp(credentials);
    if (response.error) setError(response.error);
    setIsLoading(false);
    return response;
  };

  const signInWithGoogle = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {},
    });
    if (oauthError) {
      setError(oauthError);
      setIsLoading(false);
    }
    // No explicit data return here, session updates via onAuthStateChange
  };

  const signOut = async (): Promise<{ error: AuthError | null }> => {
    setIsLoading(true);
    setError(null);
    const { error: signOutError } = await supabase.auth.signOut();
    if (signOutError) setError(signOutError);
    globalAccessToken = null;
    setLocalAccessToken(null);
    setIsLoading(false);
    return { error: signOutError };
  };

  const value: AuthContextType = {
    session,
    user,
    isLoading,
    error,
    signInWithPassword,
    signUpWithPassword,
    signInWithGoogle,
    signOut,
    accessToken: localAccessToken, // Corrected: use the state variable here
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