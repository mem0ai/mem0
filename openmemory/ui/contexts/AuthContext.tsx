"use client";

import React, { createContext, useContext, useEffect, useState, ReactNode, useCallback } from 'react';
import {
  Session, User, AuthError, AuthChangeEvent,
  AuthResponse, // For signIn and signUp
  SignInWithPasswordCredentials,
  SignUpWithPasswordCredentials
} from '@supabase/supabase-js'; // Added more specific types
import { supabase } from '../lib/supabaseClient';
import { useDispatch } from 'react-redux'; // Import useDispatch
import { setUserId } from '@/store/profileSlice'; // Import setUserId
import { usePostHog } from 'posthog-js/react';

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
  signInWithGitHub: () => Promise<void>; // Adding GitHub sign-in
  signInLocalDev: () => Promise<void>; // Local development sign-in
  signOut: () => Promise<{ error: AuthError | null }>; // signOut returns { error }
  accessToken: string | null;
  isLocalDev: boolean; // Flag to indicate if we're in local development mode
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AuthError | null>(null);
  const [localAccessToken, setLocalAccessToken] = useState<string | null>(null);
  const dispatch = useDispatch();
  const posthog = usePostHog();

  // Define updateTokenAndProfile in the component scope
  const updateTokenAndProfile = useCallback((currentSession: Session | null) => {
    const token = currentSession?.access_token ?? null;
    setLocalAccessToken(token);
    globalAccessToken = token;
    console.log('AuthContext: globalAccessToken updated:', globalAccessToken);

    // This handles the nested user object from Supabase vs the flat one in local dev
    const userObject = currentSession?.user && 'user' in currentSession.user ? (currentSession.user as any).user : currentSession?.user;
    setUser(userObject ?? null);
    
    if (userObject) {
      dispatch(setUserId(userObject.id));
    } else {
      dispatch(setUserId(null as any)); 
    }
  }, [dispatch]);

  // Check if we're in local development mode
  const isLocalDev = Boolean(process.env.NEXT_PUBLIC_USER_ID);

  useEffect(() => {
    setIsLoading(true);
    
    if (isLocalDev) {
      console.log('AuthContext: Local development mode detected - not auto-logging in');
      // In local dev mode, don't auto-login, just set loading to false
      setIsLoading(false);
    } else {
      // Normal Supabase authentication for production
      supabase.auth.getSession().then(({ data: { session: currentSession } }) => {
        setSession(currentSession);
        updateTokenAndProfile(currentSession);
        setIsLoading(false);
      });
    }

    // Only set up auth listener if not in local development mode
    const { data: authListener } = isLocalDev ? { data: { subscription: null } } : supabase.auth.onAuthStateChange(
      (event: AuthChangeEvent, currentSession: Session | null) => {
        setSession(currentSession);
        updateTokenAndProfile(currentSession);
        setIsLoading(false);
        setError(null);

        // 📊 Track authentication events with PostHog
        if (posthog && currentSession?.user && event === 'SIGNED_IN') {
          // Identify the user for the People section
          posthog.identify(currentSession.user.id, {
            email: currentSession.user.email,
            user_id: currentSession.user.id,
            name: currentSession.user.user_metadata?.full_name || currentSession.user.user_metadata?.name,
            provider: currentSession.user.app_metadata?.provider || 'email'
          });
          
          posthog.capture('user_signed_in', {
            user_id: currentSession.user.id,
            email: currentSession.user.email,
            provider: currentSession.user.app_metadata?.provider || 'email'
          });
        }
      }
    );

    return () => {
      authListener.subscription?.unsubscribe();
    };
  }, [updateTokenAndProfile, posthog, isLocalDev]);

  const signInWithPassword = async (
    credentials: SignInWithPasswordCredentials
  ): Promise<AuthResponse> => {
    setIsLoading(true);
    setError(null);
    const response = await supabase.auth.signInWithPassword(credentials);
    if (response.error) setError(response.error);
    // onAuthStateChange will handle updating user and token states
    setIsLoading(false);
    return response;
  };

  const signUpWithPassword = async (
    credentials: SignUpWithPasswordCredentials
  ): Promise<AuthResponse> => {
    setIsLoading(true);
    setError(null);
    const response = await supabase.auth.signUp(credentials);
    if (response.error) {
      setError(response.error);
    } else if (response.data.user && posthog) {
      // 📊 Track successful signup with PostHog
      posthog.capture('user_signed_up', {
        user_id: response.data.user.id,
        email: response.data.user.email,
        provider: 'email'
      });
    }
    // onAuthStateChange will handle updating user and token states
    setIsLoading(false);
    return response;
  };

  const signInWithGoogle = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: {
          prompt: 'select_account',
        },
      },
    });
    if (oauthError) {
      setError(oauthError);
      setIsLoading(false);
    }
    // No explicit data return here, session updates via onAuthStateChange
  };

  const signInWithGitHub = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: 'github',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: {
          prompt: 'select_account',
        },
      },
    });
    if (oauthError) {
      setError(oauthError);
      setIsLoading(false);
    }
    // No explicit data return here, session updates via onAuthStateChange
  };

  const signInLocalDev = async (): Promise<void> => {
    if (!isLocalDev) {
      setError({ message: 'Local development sign-in only available in development mode' } as AuthError);
      return;
    }

    setIsLoading(true);
    setError(null);
    
    const localUserId = process.env.NEXT_PUBLIC_USER_ID;
    console.log('AuthContext: Signing in local dev user:', localUserId);
    
    // Create a mock user and session for local development
    const mockUser: User = {
      id: localUserId!,
      app_metadata: { provider: 'local' },
      user_metadata: { name: 'Local Dev User' },
      aud: 'local',
      created_at: new Date().toISOString(),
      email: 'local@example.com',
    } as User;
    
    const mockSession: Session = {
      access_token: 'local-dev-token',
      refresh_token: 'local-dev-refresh-token',
      expires_in: 3600,
      expires_at: new Date().getTime() + 3600000,
      user: mockUser,
    } as Session;
    
    // Set the mock session and user
    setSession(mockSession);
    updateTokenAndProfile(mockSession);
    setIsLoading(false);
  };

  const signOut = async (): Promise<{ error: AuthError | null }> => {
    setIsLoading(true);
    setError(null);
    
    // 📊 Track sign out with PostHog
    if (posthog && user) {
      posthog.capture('user_signed_out', {
        user_id: user.id,
        email: user.email
      });
    }
    
    if (isLocalDev) {
      // In local dev mode, just clear the session
      updateTokenAndProfile(null);
      setIsLoading(false);
      return { error: null };
    } else {
      // Normal Supabase sign out for production
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) {
        setError(signOutError);
      } else {
        updateTokenAndProfile(null); // Now callable here
      }
      setIsLoading(false);
      return { error: signOutError };
    }
  };

  const value: AuthContextType = {
    session,
    user,
    isLoading,
    error,
    signInWithPassword,
    signUpWithPassword,
    signInWithGoogle,
    signInWithGitHub,
    signInLocalDev,
    signOut,
    accessToken: localAccessToken, // Corrected: use the state variable here
    isLocalDev,
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