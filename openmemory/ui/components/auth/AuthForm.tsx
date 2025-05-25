'use client';

import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Input } from "@/components/ui/input"; 
import { Button } from "@/components/ui/button"; 
import { Label } from "@/components/ui/label"; 
import { Icons } from "@/components/icons"; // Assuming you have an icons component for Google

export const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const { signInWithPassword, signUpWithPassword, signInWithGoogle, error, isLoading, user } = useAuth();
  const router = useRouter();

  // Redirect to dashboard when user becomes authenticated
  React.useEffect(() => {
    if (user) {
      router.push('/dashboard');
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
        // The useEffect above will handle the redirect when user state updates
      }
    } else {
      const { error: signUpError } = await signUpWithPassword({ email, password });
      if (!signUpError) {
        setMessage('Signup successful! Please check your email to verify your account if required, then log in.');
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
    // The useEffect above will handle the redirect when user state updates
  };

  React.useEffect(() => {
    if (error && !message) {
      setMessage(error.message);
    }
  }, [error, message]);

  return (
    <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[350px]">
      <div className="flex flex-col space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">
          {isLogin ? 'Welcome back' : 'Create an account'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isLogin ? 'Enter your email and password to sign in' : 'Enter your email and password to sign up'}
        </p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-1">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="name@example.com"
            disabled={isLoading}
          />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="Your password"
            disabled={isLoading}
          />
        </div>
        <Button type="submit" disabled={isLoading} className="w-full">
          {isLoading ? <Icons.spinner className="mr-2 h-4 w-4 animate-spin" /> : (isLogin ? 'Login' : 'Sign Up')}
        </Button>
      </form>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            Or continue with
          </span>
        </div>
      </div>

      <Button variant="outline" type="button" disabled={isLoading} onClick={handleGoogleSignIn} className="w-full">
        {isLoading ? (
          <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Icons.google className="mr-2 h-4 w-4" /> // Assuming Icons.google exists
        )}
        Google
      </Button>

      <p className="px-8 text-center text-sm text-muted-foreground">
        <button
          onClick={() => { setIsLogin(!isLogin); setMessage(''); }}
          className="underline underline-offset-4 hover:text-primary"
          disabled={isLoading}
        >
          {isLogin ? 'Need an account? Sign Up' : 'Have an account? Login'}
        </button>
      </p>
      {message && <p className={`mt-4 text-sm ${message.startsWith('Signup successful') ? 'text-green-600' : 'text-red-600'}`}>{message}</p>}
    </div>
  );
}; 