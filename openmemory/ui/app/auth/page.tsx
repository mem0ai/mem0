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
      <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 via-black to-blue-900/20" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-purple-900/10 via-transparent to-transparent" />
      
      {/* Animated background particles */}
      <div className="absolute inset-0">
        {[...Array(50)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 bg-purple-400/30 rounded-full"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
            }}
            animate={{
              y: [0, -20, 0],
              opacity: [0.3, 0.8, 0.3],
            }}
            transition={{
              duration: 3 + Math.random() * 2,
              repeat: Infinity,
              delay: Math.random() * 2,
            }}
          />
        ))}
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
        <div className="w-full max-w-md">
          {/* Logo/Branding */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center mb-8"
          >
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent mb-2">
              Jean Memory
            </h1>
            <p className="text-zinc-400 text-lg">
              Your AI memory, everywhere
            </p>
          </motion.div>

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
        <div className="absolute inset-0 bg-gradient-conic from-purple-600 via-blue-600 to-purple-600 blur-3xl animate-spin-slow" />
      </div>
    </div>
  );
};

export default AuthPage; 