"use client";

import React, { useState } from 'react';
import { App } from '@/store/appsSlice';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Copy, Check, Terminal } from 'lucide-react';
import { constants } from "@/components/shared/source-app";
import Image from 'next/image';

interface InstallModalProps {
  app: App | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InstallModal({ app, open, onOpenChange }: InstallModalProps) {
  const [copied, setCopied] = useState(false);
  const { user } = useAuth();
  const userId = user?.id || 'your-user-id';
  
  if (!app) return null;

  const appConfig = constants[app.name as keyof typeof constants] || constants.default;
  const MCP_URL = "https://api.jeanmemory.com"; // This should be the production URL for installs
  const installCommand = `npx install-mcp ${MCP_URL}/mcp/${app.name}/sse/${userId} --client ${app.name}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-zinc-900 border-zinc-800 text-white">
        <DialogHeader className="mb-4">
          <DialogTitle className="flex items-center gap-3 text-2xl">
            {appConfig.iconImage ? (
              <div className="w-8 h-8 rounded-lg bg-zinc-700 flex items-center justify-center overflow-hidden">
                <Image src={appConfig.iconImage} alt={appConfig.name} width={32} height={32} />
              </div>
            ) : (
              <div className="w-8 h-8 flex items-center justify-center">{appConfig.icon}</div>
            )}
            Connect to {appConfig.name}
          </DialogTitle>
          <DialogDescription className="text-zinc-400 pt-2">
            Follow these steps to enable Jean Memory for {appConfig.name}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div>
            <h3 className="font-semibold text-lg mb-2">1. Prerequisite: Have {appConfig.name} Installed</h3>
            <p className="text-zinc-400">
              Ensure you have the {appConfig.name} application downloaded and installed on your computer.
            </p>
          </div>
          
          <div>
            <h3 className="font-semibold text-lg mb-2">2. Run the Install Command</h3>
            <p className="text-zinc-400 mb-3">
              Open your terminal (like Terminal on Mac, or Command Prompt/PowerShell on Windows) and paste the following command:
            </p>
            <div className="relative group bg-zinc-950 border border-zinc-700 rounded-lg p-4 font-mono text-sm text-zinc-300">
              <code>{installCommand}</code>
              <Button
                size="icon"
                variant="ghost"
                className="absolute top-2 right-2 h-8 w-8 opacity-50 group-hover:opacity-100 transition-opacity"
                onClick={handleCopy}
              >
                {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-lg mb-2">3. Restart {appConfig.name}</h3>
            <p className="text-zinc-400">
              After the command completes, fully close and restart {appConfig.name}. Jean Memory will now be active.
            </p>
          </div>
        </div>
        
        <div className="mt-8 pt-6 border-t border-zinc-800 text-center">
            <Button onClick={() => onOpenChange(false)}>Done</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
} 