"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { Key, Plus, Trash2, Copy, AlertTriangle, X, Check, Crown, Shield, User } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

// --- Type Definitions ---

interface ApiKey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

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



// --- Main Page Component ---

export default function ApiKeysPage() {
  const { user, accessToken } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for modals
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isNewKeyModalOpen, setIsNewKeyModalOpen] = useState(false);
  
  // State for key management
  const [newKeyName, setNewKeyName] = useState("");
  const [newlyGeneratedKey, setNewlyGeneratedKey] = useState<{key: string, info: ApiKey} | null>(null);
  const [keyToRevoke, setKeyToRevoke] = useState<ApiKey | null>(null);
  const [copied, setCopied] = useState(false);

  // State for profile editing
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editFirstname, setEditFirstname] = useState("");
  const [editLastname, setEditLastname] = useState("");
  const [profileUpdateLoading, setProfileUpdateLoading] = useState(false);

  const handleApiError = (error: any, response?: Response) => {
    // Check if this is a subscription-related error (402 status)
    if (response?.status === 402 && typeof error.detail === 'object' && error.detail.error === 'subscription_required') {
      // Show a simple toast-style error instead of the annoying modal
      const errorMessage = error.detail?.message || "This feature requires a Pro subscription.";
      setError(errorMessage);
    } else {
      // Handle as regular error
      const errorMessage = typeof error.detail === 'string' ? error.detail : error.detail?.message || error.message || 'An error occurred';
      setError(errorMessage);
    }
  };

  const fetchProfile = async () => {
    if (!accessToken) return;
    
    try {
      const response = await fetch("/api/v1/profile/", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setProfile(data);
        // Initialize edit fields with current values
        setEditFirstname(data.firstname || "");
        setEditLastname(data.lastname || "");
      }
    } catch (err: any) {
      console.error("Failed to fetch profile:", err);
    }
  };

  const fetchKeys = async () => {
    if (!accessToken) {
      setError("Authentication token not available.");
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      const response = await fetch("/api/v1/keys/", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!response.ok) {
        const errorData = await response.json();
        handleApiError(errorData, response);
        return;
      }
      const data = await response.json();
      setKeys(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (user && accessToken) {
      fetchProfile();
      fetchKeys();
    }
  }, [user, accessToken]);

  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || !accessToken) return;

    try {
      const response = await fetch("/api/v1/keys/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ name: newKeyName }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        handleApiError(errorData, response);
        return;
      }
      
      const data = await response.json();
      setNewlyGeneratedKey(data);
      setIsGenerateModalOpen(false);
      setIsNewKeyModalOpen(true);
      setNewKeyName("");
      fetchKeys(); // Refresh the list
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRevokeKey = async () => {
    if (!keyToRevoke || !accessToken) return;

    try {
      const response = await fetch(`/api/v1/keys/${keyToRevoke.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        handleApiError(errorData, response);
        return;
      }

      setKeys(keys.filter(k => k.id !== keyToRevoke.id));
      setIsConfirmModalOpen(false);
      setKeyToRevoke(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
    }, 2000);
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken) return;

    setProfileUpdateLoading(true);
    try {
      const response = await fetch("/api/v1/profile/", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          firstname: editFirstname.trim() || null,
          lastname: editLastname.trim() || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to update profile");
      }

      const updatedProfile = await response.json();
      setProfile(updatedProfile);
      setIsEditingProfile(false);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setProfileUpdateLoading(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditingProfile(false);
    setEditFirstname(profile?.firstname || "");
    setEditLastname(profile?.lastname || "");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div
          className="flex justify-between items-center mb-8"
        >
          <div>
            <h1 className="text-3xl font-bold text-foreground mb-2 flex items-center"><Key className="mr-3" /> API Keys</h1>
            <p className="text-muted-foreground">
              Build agents with memory.
            </p>
          </div>
          <Button variant="outline" onClick={() => setIsGenerateModalOpen(true)}>
            <Plus size={20} className="mr-2" />
            Generate New Key
          </Button>
        </div>

        {/* Personal Information Card */}
        {profile && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5 text-blue-500" />
                Personal Information
              </CardTitle>
              <CardDescription>
                Manage your personal details
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!isEditingProfile ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">First Name</div>
                    <div className="text-lg">{profile.firstname || 'Not set'}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">Last Name</div>
                    <div className="text-lg">{profile.lastname || 'Not set'}</div>
                  </div>
                  <div className="col-span-2 mt-4">
                    <Button 
                      variant="outline" 
                      onClick={() => setIsEditingProfile(true)}
                    >
                      Edit Personal Information
                    </Button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleUpdateProfile} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="firstname" className="block text-sm font-medium text-muted-foreground mb-2">
                        First Name
                      </label>
                      <Input
                        id="firstname"
                        type="text"
                        value={editFirstname}
                        onChange={(e) => setEditFirstname(e.target.value)}
                        placeholder="Enter your first name"
                        maxLength={100}
                      />
                    </div>
                    <div>
                      <label htmlFor="lastname" className="block text-sm font-medium text-muted-foreground mb-2">
                        Last Name
                      </label>
                      <Input
                        id="lastname"
                        type="text"
                        value={editLastname}
                        onChange={(e) => setEditLastname(e.target.value)}
                        placeholder="Enter your last name"
                        maxLength={100}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      type="submit" 
                      disabled={profileUpdateLoading}
                    >
                      {profileUpdateLoading ? 'Saving...' : 'Save Changes'}
                    </Button>
                    <Button 
                      type="button" 
                      variant="outline" 
                      onClick={handleCancelEdit}
                      disabled={profileUpdateLoading}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        )}

        {/* Subscription Status Card */}
        {profile && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {profile.subscription_tier === 'ENTERPRISE' ? (
                  <Shield className="h-5 w-5 text-purple-500" />
                ) : profile.subscription_tier === 'PRO' ? (
                  <Crown className="h-5 w-5 text-yellow-500" />
                ) : (
                  <User className="h-5 w-5 text-gray-500" />
                )}
                Account Status
              </CardTitle>
              <CardDescription>
                Your current subscription and account details
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Subscription Tier</div>
                  <div className={`text-lg font-semibold ${
                    profile.subscription_tier === 'ENTERPRISE' ? 'text-purple-500' :
                    profile.subscription_tier === 'PRO' ? 'text-yellow-500' : 
                    'text-gray-500'
                  }`}>
                    {profile.subscription_tier === 'ENTERPRISE' ? 'Enterprise' :
                     profile.subscription_tier === 'PRO' ? 'Pro' : 
                     'Free'}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Status</div>
                  <div className={`text-lg font-semibold ${
                    profile.subscription_status === 'active' ? 'text-green-500' :
                    profile.subscription_status === 'past_due' ? 'text-yellow-500' :
                    profile.subscription_status === 'canceled' ? 'text-red-500' :
                    'text-gray-500'
                  }`}>
                    {profile.subscription_status === 'active' ? 'Active' :
                     profile.subscription_status === 'past_due' ? 'Past Due' :
                     profile.subscription_status === 'canceled' ? 'Canceled' :
                     profile.subscription_status === 'incomplete' ? 'Incomplete' :
                     profile.subscription_status || 'Not Set'}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Account Email</div>
                  <div className="text-lg">{profile.email || 'Not set'}</div>
                </div>
              </div>
              {profile.subscription_tier === 'FREE' && (
                <div className="mt-4 p-3 bg-muted rounded-md">
                  <p className="text-sm text-muted-foreground">
                    Upgrade to Pro for API access, SMS features, and unlimited memory storage.{' '}
                    <a href="/pro" className="text-primary hover:underline">
                      Learn more →
                    </a>
                  </p>
                </div>
              )}
              {profile.subscription_tier === 'PRO' && profile.subscription_status !== 'active' && (
                <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700/50 rounded-md">
                  <p className="text-sm text-yellow-800 dark:text-yellow-300">
                    <strong>Subscription Issue:</strong> Your Pro subscription is {profile.subscription_status}. 
                    Please check your payment method or contact support at{' '}
                    <a href="mailto:jonathan@jeantechnologies.com" className="underline">
                      jonathan@jeantechnologies.com
                    </a>
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {isLoading && <p>Loading keys...</p>}
        {error && <p className="text-destructive">{error}</p>}

        {!isLoading && !error && (
          <Card>
            <CardContent className="p-0">
              {keys.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Last Used</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keys.map((key) => (
                      <TableRow key={key.id}>
                        <TableCell className="font-medium">{key.name}</TableCell>
                        <TableCell>{new Date(key.created_at).toLocaleDateString()}</TableCell>
                        <TableCell>{key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" onClick={() => { setKeyToRevoke(key); setIsConfirmModalOpen(true); }}>
                            <Trash2 size={16} className="mr-2" />
                            Revoke
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="flex flex-col items-center justify-center p-12 text-center">
                  <Key className="w-12 h-12 text-muted-foreground mb-4" />
                  <h3 className="text-xl font-semibold mb-2">No API Keys Yet</h3>
                  <p className="text-muted-foreground mb-6">
                    Generate your first key to connect your agents and applications.
                  </p>
                  <Button onClick={() => setIsGenerateModalOpen(true)}>
                    <Plus size={20} className="mr-2" />
                    Generate New Key
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={isGenerateModalOpen} onOpenChange={setIsGenerateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate New API Key</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleGenerateKey}>
            <label htmlFor="keyName" className="block text-muted-foreground mb-2">Key Name</label>
            <Input
              id="keyName"
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., My Personal Agent"
              className="mb-4"
            />
            <DialogFooter className="gap-2">
              <DialogClose asChild>
                <Button type="button" variant="secondary">Cancel</Button>
              </DialogClose>
              <Button type="submit" disabled={!newKeyName.trim()}>Generate</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isNewKeyModalOpen} onOpenChange={setIsNewKeyModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>API Key Generated</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Secure Your Key</AlertTitle>
              <AlertDescription>
                Please copy this key and store it securely. You will not be able to see it again.
              </AlertDescription>
            </Alert>
            <div className="bg-muted p-3 rounded-md">
              <div className="flex items-center justify-between gap-2">
                <code className="text-sm font-mono break-all flex-1">{newlyGeneratedKey?.key}</code>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="flex-shrink-0" 
                  onClick={() => copyToClipboard(newlyGeneratedKey?.key || '')}
                >
                  {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setIsNewKeyModalOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {keyToRevoke && (
        <Dialog open={isConfirmModalOpen} onOpenChange={setIsConfirmModalOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Are you sure?</DialogTitle>
              <DialogDescription>
                Revoking this key is irreversible. Any applications using it will no longer be able to access Jean.
              </DialogDescription>
            </DialogHeader>
            <p className="font-semibold">{keyToRevoke.name}</p>
            <DialogFooter className="gap-2">
              <DialogClose asChild>
                <Button type="button" variant="secondary">Cancel</Button>
              </DialogClose>
              <Button variant="destructive" onClick={handleRevokeKey}>
                Yes, Revoke Key
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

    </div>
  );
} 