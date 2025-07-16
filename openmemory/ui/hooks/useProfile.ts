import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface Profile {
  user_id: string;
  email: string | null;
  name: string | null;
  firstname: string | null;
  lastname: string | null;
  subscription_tier: string;
  subscription_status: string | null;
  phone_number: string | null;
  phone_verified: boolean;
  sms_enabled: boolean;
}

export function useProfile() {
  const { user, accessToken } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProfile() {
      if (!user?.id || !accessToken) {
        setIsLoading(false);
        return;
      }

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8765';
        const response = await fetch(`${API_URL}/api/v1/profile/`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setProfile(data);
          setError(null);
        } else {
          setError('Failed to fetch profile');
        }
      } catch (err) {
        console.error('Error fetching profile:', err);
        setError('Failed to fetch profile');
      } finally {
        setIsLoading(false);
      }
    }

    fetchProfile();
  }, [user?.id, accessToken]);

  // Helper function to get display name
  const getDisplayName = () => {
    if (!profile) return null;
    
    if (profile.firstname || profile.lastname) {
      return `${profile.firstname || ''} ${profile.lastname || ''}`.trim();
    }
    
    return profile.name || profile.email?.split('@')[0] || 'User';
  };

  return { profile, isLoading, error, getDisplayName };
}