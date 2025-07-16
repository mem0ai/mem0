'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

export default function AuthCallbackPage() {
  const router = useRouter();
  const { user, isLoading, accessToken } = useAuth();

  useEffect(() => {
    // Give Supabase a moment to process the auth callback
    const timer = setTimeout(async () => {
      if (!isLoading) {
        if (user && accessToken) {
          // Check for pending profile update from OAuth signup
          const pendingUpdate = sessionStorage.getItem('pendingProfileUpdate');
          if (pendingUpdate) {
            try {
              const profileData = JSON.parse(pendingUpdate);
              const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8765';
              
              const response = await fetch(`${API_URL}/api/v1/profile/`, {
                method: 'PUT',
                headers: {
                  'Authorization': `Bearer ${accessToken}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify(profileData),
              });
              
              if (response.ok) {
                console.log('Successfully updated profile with name information from OAuth signup');
              } else {
                console.warn('Failed to update profile with name information from OAuth signup');
              }
            } catch (error) {
              console.warn('Error updating profile with name information from OAuth signup:', error);
            } finally {
              // Clear the pending update regardless of success/failure
              sessionStorage.removeItem('pendingProfileUpdate');
            }
          }
          
          // User is authenticated, redirect to dashboard
          console.log('Auth callback: User authenticated, redirecting to dashboard');
          router.replace('/dashboard');
        } else {
          // No user found, redirect to auth page
          console.log('Auth callback: No user found, redirecting to auth');
          router.replace('/auth');
        }
      }
    }, 1000); // Wait 1 second for auth state to settle

    return () => clearTimeout(timer);
  }, [user, isLoading, accessToken, router]);

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-4"></div>
        <div className="text-white">Completing authentication...</div>
        <div className="text-zinc-400 text-sm mt-2">Please wait while we sign you in</div>
      </div>
    </div>
  );
} 