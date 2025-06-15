"use client";

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppSync } from '@/hooks/useAppSync';
import { DashboardApp } from './AppCard';

interface SyncModalProps {
  app: DashboardApp | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSyncStart: (appId: string, taskId: string) => void;
}

export function SyncModal({ app, open, onOpenChange, onSyncStart }: SyncModalProps) {
  const [inputValue, setInputValue] = useState('');
  
  const { isLoading, handleSync } = useAppSync({ 
    app, 
    onSyncStart: (appId, taskId) => {
      if (app) {
        onSyncStart(appId, taskId);
      }
      onOpenChange(false); // Close modal on sync start
    }
  });

  if (!app) return null;

  const handleConfirm = async () => {
    const success = await handleSync(inputValue);
    if (success) {
      setInputValue('');
    }
  };
  
  const getPlaceholder = () => {
    if (app.id === 'twitter') return '@username or profile URL';
    if (app.id === 'substack') return 'username.substack.com';
    return 'Enter value';
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect {app.name}</DialogTitle>
          <DialogDescription>
            Enter your {app.name} {app.id === 'twitter' ? 'username' : 'URL'} to sync your data.
            This will start a background job to import your content as memories.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Input 
            placeholder={getPlaceholder()}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isLoading}
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? `Syncing ${app.name}...` : `Sync ${app.name}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 