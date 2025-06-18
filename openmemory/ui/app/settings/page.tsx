"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { Key, Plus, Trash2, Copy, AlertTriangle, X, Check } from 'lucide-react';
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



// --- Main Page Component ---

export default function ApiKeysPage() {
  const { user, accessToken } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
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