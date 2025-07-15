'use client';
import React from 'react';
import { AuthForm } from '../../components/auth/AuthForm';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';

const AuthPage = () => {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!isLoading && user) {
      // Force redirect to dashboard for authenticated users
      router.replace('/dashboard');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  if (!isLoading && user) {
    // This case should be handled by the redirect, but as a fallback:
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Already logged in. Redirecting to dashboard...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 bg-gradient-to-b from-blue-950/60 via-transparent to-slate-950/60" />
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-black/80 to-black" />
      
      {/* Main Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
        <div className="w-full max-w-md">
          {/* Auth Form */}
          <AuthForm />

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="mt-8 text-center"
          >
            <p className="text-xs text-zinc-500">
              Secure • Private • Universal
            </p>
          </motion.div>
        </div>
      </div>

      {/* Subtle animated gradient */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute inset-0 bg-gradient-conic from-slate-700 via-blue-900 to-slate-700 blur-3xl animate-spin-slow" />
      </div>
    </div>
  );
};

export default AuthPage; 