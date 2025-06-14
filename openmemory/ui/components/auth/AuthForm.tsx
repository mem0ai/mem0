'use client';

import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Input } from "@/components/ui/input"; 
import { Button } from "@/components/ui/button"; 
import { Label } from "@/components/ui/label"; 
import { Icons } from "@/components/icons";
import { motion } from "framer-motion";

export const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const { signInWithPassword, signUpWithPassword, signInWithGoogle, signInWithGitHub, error, isLoading, user, isLocalDev } = useAuth();
  const router = useRouter();

  // Redirect to dashboard when user becomes authenticated
  React.useEffect(() => {
    if (user) {
      router.replace('/dashboard');
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    let authError = null;

    if (isLogin) {
      const { error: signInError } = await signInWithPassword({ email, password });
      authError = signInError;
      if (!signInError) {
        setMessage('Login successful! Redirecting...');
      }
    } else {
      const { error: signUpError } = await signUpWithPassword({ email, password });
      if (!signUpError) {
        setMessage('Account created! Please check your email to verify your account.');
      } else {
        authError = signUpError;
      }
    }

    if (authError) {
      setMessage(authError.message);
    }
  };
  
  const handleGoogleSignIn = async () => {
    setMessage('');
    await signInWithGoogle();
  };

  const handleGitHubSignIn = async () => {
    setMessage('');
    await signInWithGitHub();
  };

  React.useEffect(() => {
    if (error && !message) {
      setMessage(error.message);
    }
  }, [error, message]);

  return (
    <div className="w-full max-w-md mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="bg-zinc-900/50 backdrop-blur-sm border border-zinc-800 rounded-2xl p-8 shadow-2xl"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <motion.h1 
            className="text-3xl font-bold bg-gradient-to-r from-neutral-400 via-neutral-200 to-neutral-400 bg-clip-text text-transparent mb-2"
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3 }}
          >
            {isLogin ? 'Sign into your Vault' : 'Create your Vault'}
          </motion.h1>
          <p className="text-zinc-400">
            {isLogin ? 'See your memories' : 'Create an account to secure your memories'}
          </p>
        </div>

        {!isLocalDev && (
          <>
            {/* Social Sign In */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="space-y-3 mb-6"
            >
              <Button 
                variant="outline" 
                type="button" 
                disabled={isLoading} 
                onClick={handleGoogleSignIn} 
                className="w-full h-11 bg-zinc-900 hover:bg-zinc-800 text-white border-zinc-700 font-medium text-base"
              >
                {isLoading ? (
                  <Icons.spinner className="mr-3 h-5 w-5 animate-spin" />
                ) : (
                  <Icons.google className="mr-3 h-5 w-5" />
                )}
                Continue with Google
              </Button>
              <Button 
                variant="outline" 
                type="button" 
                disabled={isLoading} 
                onClick={handleGitHubSignIn} 
                className="w-full h-11 bg-zinc-900 hover:bg-zinc-800 text-white border-zinc-700 font-medium text-base"
              >
                {isLoading ? (
                  <Icons.spinner className="mr-3 h-5 w-5 animate-spin" />
                ) : (
                  <Icons.github className="mr-3 h-5 w-5" />
                )}
                Continue with GitHub
              </Button>
            </motion.div>

            {/* Divider */}
            <div className="relative mb-6">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-zinc-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-zinc-900 px-3 text-zinc-500 font-medium">
                  Or continue with email
                </span>
              </div>
            </div>
          </>
        )}

        {/* Email/Password Form */}
        <motion.form 
          onSubmit={handleSubmit} 
          className="space-y-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="space-y-2">
            <Label htmlFor="email" className="text-zinc-300 font-medium">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="your@email.com"
              disabled={isLoading}
              className="h-11 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-slate-500 focus:ring-slate-500/20"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="password" className="text-zinc-300 font-medium">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder={isLogin ? "Enter your password" : "Create a secure password"}
              disabled={isLoading}
              className="h-11 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-slate-500 focus:ring-slate-500/20"
            />
            {!isLogin && (
              <p className="text-xs text-zinc-500 mt-1">
                At least 8 characters recommended (mix of letters and numbers is fine)
              </p>
            )}
          </div>

          <Button 
            type="submit" 
            disabled={isLoading} 
            className="w-full h-11 bg-slate-100 hover:bg-slate-200 text-black font-medium mt-6"
          >
            {isLoading ? (
              <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              isLogin ? 'Sign In' : 'Create Account'
            )}
          </Button>
        </motion.form>

        {/* Toggle between login/signup */}
        <div className="mt-6 text-center">
          <button
            onClick={() => { 
              setIsLogin(!isLogin); 
              setMessage(''); 
              setEmail('');
              setPassword('');
            }}
            className="text-sm text-zinc-400 hover:text-white transition-colors font-medium"
            disabled={isLoading}
          >
            {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
          </button>
        </div>

        {/* Message display */}
        {message && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-4 p-3 rounded-lg text-sm text-center border ${
              message.includes('successful') || message.includes('created') 
                ? 'bg-green-900/20 text-green-300 border-green-800/50' 
                : 'bg-red-900/20 text-red-300 border-red-800/50'
            }`}
          >
            {message}
          </motion.div>
        )}

        {/* Additional info for new users */}
        {!isLogin && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="mt-6 space-y-3"
          >
            <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <p className="text-xs text-blue-300 text-center font-medium mb-2">
                🚀 Join thousands of users who trust Jean Memory
              </p>
              <div className="text-xs text-blue-200/80 space-y-1">
                <p>• Works with Claude, ChatGPT, Gemini, and more</p>
                <p>• Memories sync across all your AI conversations</p>
                <p>• One-click setup with your favorite AI tools</p>
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}; 