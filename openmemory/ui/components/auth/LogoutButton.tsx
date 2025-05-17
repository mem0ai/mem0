'use client';

import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
// import { Button } from "@/components/ui/button"; // Example

export const LogoutButton = () => {
  const { signOut, isLoading, error } = useAuth();

  const handleLogout = async () => {
    await signOut();
    // Redirect or UI update should happen based on AuthContext state change
  };

  return (
    <>
      <button onClick={handleLogout} disabled={isLoading} style={{ padding: '8px 15px'}}>
        {isLoading ? 'Logging out...' : 'Logout'}
      </button>
      {error && <p style={{ color: 'red' }}>Error: {error.message}</p>}
    </>
  );
}; 