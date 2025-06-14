'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

export default function AuthCallbackPage() {
  const router = useRouter();
  const { user, isLoading } = useAuth();

  useEffect(() => {
    // Give Supabase a moment to process the auth callback
    const timer = setTimeout(() => {
      if (!isLoading) {
        if (user) {
          // User is authenticated, redirect to dashboard
          console.log('Auth callback: User authenticated, redirecting to dashboard');
          router.replace('/dashboard-new');
        } else {
          // No user found, redirect to auth page
          console.log('Auth callback: No user found, redirecting to auth');
          router.replace('/auth');
        }
      }
    }, 1000); // Wait 1 second for auth state to settle

    return () => clearTimeout(timer);
  }, [user, isLoading, router]);

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