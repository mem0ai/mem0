'use client';
import React from 'react';
import { AuthForm } from '../../components/auth/AuthForm';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation'; // For App Router

const AuthPage = () => {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!isLoading && user) {
      router.push('/dashboard'); // Redirect to dashboard if already logged in
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return <div style={{ textAlign: 'center', marginTop: '50px' }}>Loading...</div>;
  }

  if (!isLoading && user) {
    // This case should be handled by the redirect, but as a fallback:
    return <div style={{ textAlign: 'center', marginTop: '50px' }}>Already logged in. Redirecting...</div>;
  }

  return (
    <div>
      <AuthForm />
    </div>
  );
};

export default AuthPage; 