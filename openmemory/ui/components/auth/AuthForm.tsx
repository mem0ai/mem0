'use client';

import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
// You will likely want to use some UI components from your existing library (e.g., @radix-ui, lucide-react)
// For simplicity, this example uses basic HTML elements.
// import { Input } from "@/components/ui/input"; // Example if using Shadcn/ui
// import { Button } from "@/components/ui/button"; // Example if using Shadcn/ui
// import { Label } from "@/components/ui/label"; // Example if using Shadcn/ui

export const AuthForm = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const { signInWithPassword, signUpWithPassword, signInWithGoogle, error, isLoading } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage('');
    let authError = null;

    if (isLogin) {
      const { error: signInError } = await signInWithPassword({ email, password });
      authError = signInError;
    } else {
      const { error: signUpError } = await signUpWithPassword({ email, password });
      // Optionally, sign in the user immediately after successful sign-up
      if (!signUpError) {
        setMessage('Signup successful! Please check your email to verify your account if required, then log in.');
        // Or automatically sign in: await signInWithPassword({ email, password });
      } else {
        authError = signUpError;
      }
    }

    if (authError) {
      setMessage(authError.message);
    } else if (isLogin) {
      // Login success is handled by onAuthStateChange, redirect or UI change should happen there
      // or in a parent component observing the user state.
      setMessage('Login successful! Redirecting...');
    }
  };
  
  const handleGoogleSignIn = async () => {
    setMessage('');
    await signInWithGoogle();
    // Error handling for Google Sign-In is managed within the AuthContext
    // and will be reflected in the `error` state from `useAuth()`.
    // Supabase handles the redirect.
  };

  // Display AuthContext error if it exists and no specific form message is set
  React.useEffect(() => {
    if (error && !message) {
      setMessage(error.message);
    }
  }, [error, message]);

  return (
    <div style={{ maxWidth: '400px', margin: 'auto', padding: '20px' }}>
      <h2>{isLogin ? 'Login' : 'Sign Up'}</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">Email:</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
            required
            style={{ width: '100%', padding: '8px', marginBottom: '10px' }}
          />
        </div>
        <div>
          <label htmlFor="password">Password:</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: '8px', marginBottom: '20px' }}
          />
        </div>
        <button type="submit" disabled={isLoading} style={{ width: '100%', padding: '10px', marginBottom: '10px' }}>
          {isLoading ? 'Processing...' : (isLogin ? 'Login' : 'Sign Up')}
        </button>
      </form>
      <button onClick={handleGoogleSignIn} disabled={isLoading} style={{ width: '100%', padding: '10px', marginBottom: '10px', background: '#db4437', color: 'white', border: 'none' }}>
        {isLoading ? 'Processing...' : 'Sign in with Google'}
      </button>
      <button onClick={() => { setIsLogin(!isLogin); setMessage(''); }} style={{ background: 'none', border: 'none', color: 'blue', cursor: 'pointer'}}>
        {isLogin ? 'Need an account? Sign Up' : 'Have an account? Login'}
      </button>
      {message && <p style={{ color: message.startsWith('Signup successful') ? 'green' : 'red', marginTop: '10px' }}>{message}</p>}
    </div>
  );
}; 