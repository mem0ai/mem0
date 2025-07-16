"use client";

import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { User, X, Check } from 'lucide-react';
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

export function ProfileCompletionBanner() {
  const { user, accessToken } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDismissed, setIsDismissed] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editFirstname, setEditFirstname] = useState("");
  const [editLastname, setEditLastname] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  useEffect(() => {
    const dismissed = localStorage.getItem('profile-completion-banner-dismissed');
    setIsDismissed(dismissed === 'true');
  }, []);

  useEffect(() => {
    async function fetchProfile() {
      if (!user?.id || !accessToken) {
        setIsLoading(false);
        return;
      }

      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8765';

      try {
        const response = await fetch(`${API_URL}/api/v1/profile/`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setProfile(data);
          setEditFirstname(data.firstname || "");
          setEditLastname(data.lastname || "");
        }
      } catch (error) {
        console.error('Error fetching profile:', error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchProfile();
  }, [user?.id, accessToken]);

  const handleDismiss = () => {
    setIsDismissed(true);
    localStorage.setItem('profile-completion-banner-dismissed', 'true');
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken) return;

    setIsUpdating(true);
    setUpdateError(null);

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8765';

    try {
      const response = await fetch(`${API_URL}/api/v1/profile/`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          firstname: editFirstname.trim() || null,
          lastname: editLastname.trim() || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update profile');
      }

      const updatedProfile = await response.json();
      setProfile(updatedProfile);
      setIsEditing(false);
      
      // If both fields are now filled, auto-dismiss the banner
      if (updatedProfile.firstname && updatedProfile.lastname) {
        handleDismiss();
      }
    } catch (error: any) {
      setUpdateError(error.message);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditFirstname(profile?.firstname || "");
    setEditLastname(profile?.lastname || "");
    setUpdateError(null);
  };

  // Don't show if loading, dismissed, or if profile is complete
  if (isLoading || isDismissed || !profile) {
    return null;
  }

  // Don't show if user already has both firstname and lastname
  if (profile.firstname && profile.lastname) {
    return null;
  }

  return (
    <Alert className="mb-6 border-blue-500">
      <div className="flex items-start gap-3">
        <User className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <AlertDescription className="text-sm">
            {!isEditing ? (
              <>
                <p className="font-semibold mb-2">
                  Complete Your Profile
                </p>
                <p className="mb-3 text-muted-foreground">
                  Help us personalize your experience by adding your first and last name.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button 
                    onClick={() => setIsEditing(true)} 
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    Add Name
                  </Button>
                  <Button 
                    onClick={handleDismiss} 
                    variant="outline" 
                    size="sm"
                  >
                    Maybe Later
                  </Button>
                </div>
              </>
            ) : (
              <form onSubmit={handleUpdate} className="space-y-3">
                <p className="font-semibold mb-3">
                  Add Your Name
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <Input
                      type="text"
                      placeholder="First Name"
                      value={editFirstname}
                      onChange={(e) => setEditFirstname(e.target.value)}
                      maxLength={100}
                      className="h-9"
                    />
                  </div>
                  <div>
                    <Input
                      type="text"
                      placeholder="Last Name"
                      value={editLastname}
                      onChange={(e) => setEditLastname(e.target.value)}
                      maxLength={100}
                      className="h-9"
                    />
                  </div>
                </div>
                {updateError && (
                  <p className="text-sm text-red-600 dark:text-red-400">
                    {updateError}
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button 
                    type="submit" 
                    size="sm" 
                    disabled={isUpdating}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {isUpdating ? (
                      <>
                        <Check className="w-3 h-3 mr-1 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save'
                    )}
                  </Button>
                  <Button 
                    type="button"
                    variant="outline" 
                    size="sm" 
                    onClick={handleCancel}
                    disabled={isUpdating}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </AlertDescription>
        </div>
        {!isEditing && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDismiss}
            className="p-1 h-auto flex-shrink-0"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </Alert>
  );
}