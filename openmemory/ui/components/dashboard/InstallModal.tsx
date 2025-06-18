"use client";

import React, { useState } from 'react';
import { App } from '@/store/appsSlice';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Copy, Check, Key, Shield, Link as LinkIcon, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { constants } from "@/components/shared/source-app";
import Image from 'next/image';
import apiClient from '@/lib/apiClient';

interface InstallModalProps {
  app: App | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSyncStart: (appId: string, taskId: string) => void;
}

export function InstallModal({ app, open, onOpenChange, onSyncStart }: InstallModalProps) {
  const [copied, setCopied] = useState(false);
  const { user, accessToken } = useAuth();
  const { toast } = useToast();
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSync = async () => {
    if (!app || !inputValue) return;

    setIsLoading(true);

    try {
      const endpoint = app.id === 'twitter' 
        ? '/api/v1/integrations/sync/twitter' 
        : '/api/v1/integrations/substack/sync';
      
      let response;
      if (app.id === 'twitter') {
        // Twitter uses query parameters
        const params = { username: inputValue.replace('@', ''), max_posts: 40 };
        response = await apiClient.post(endpoint, null, { params });
      } else {
        // Substack uses POST body
        const data = { substack_url: inputValue, max_posts: 20 };
        response = await apiClient.post(endpoint, data);
      }
      
      onSyncStart(app.id, response.data.task_id);

      toast({
        title: "Sync Started",
        description: "This may take a few minutes. Set up some of your other apps.",
      });
      
      onOpenChange(false);

    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Connection Error",
        description: error.response?.data?.detail || `Failed to connect ${app.name}. Please check the input and try again.`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!app) return null;

  const appConfig = constants[app.id as keyof typeof constants] || constants.default;
  const MCP_URL = "https://api.jeanmemory.com";
  const installCommand = `npx install-mcp ${MCP_URL}/mcp/${app.id}/sse/${user?.id} --client ${app.id}`;
  const mcpLink = `${MCP_URL}/mcp/openmemory/sse/${user?.id}`;
  const chatgptLink = `${MCP_URL}/mcp/chatgpt/sse/${user?.id}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800 text-white shadow-2xl shadow-blue-500/10">
        <DialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center mb-4">
            {appConfig.iconImage ? (
                <Image src={appConfig.iconImage} alt={app.name} width={36} height={36} />
            ) : (
                <div className="w-9 h-9 flex items-center justify-center">{appConfig.icon}</div>
            )}
          </div>
          <DialogTitle className="text-2xl font-bold">
            {app.id === 'mcp-generic' ? 'Your Universal MCP Link' : 
             app.id === 'chatgpt' ? 'Connect to ChatGPT Deep Research' :
             `Connect to ${app.name}`}
          </DialogTitle>
          <DialogDescription className="text-zinc-400 pt-1">
            {app.id === 'mcp-generic'
                ? 'Use this URL for any MCP-compatible application.'
                : app.id === 'chatgpt'
                ? 'Add Jean Memory to ChatGPT Deep Research. Enterprise account required.'
                : app.id === 'substack' || app.id === 'twitter'
                ? `Provide your ${app.name} details to sync your content.`
                : `Activate Jean Memory for ${app.name} in two simple steps.`
            }
          </DialogDescription>
        </DialogHeader>

        {app.id === 'mcp-generic' ? (
            <div className="px-4 py-2 text-center">
                <p className="text-zinc-400 text-sm mb-4">
                    Copy this URL and paste it into any MCP-compatible application to connect it with Jean Memory.
                </p>
                <div className="relative group bg-black border border-zinc-700 rounded-md p-3 font-mono text-xs text-zinc-300 flex items-center justify-between">
                    <code style={{ wordBreak: 'break-all' }}>{mcpLink}</code>
                    <Button variant="ghost" className="ml-4 text-zinc-400 hover:text-white" onClick={() => handleCopy(mcpLink)}>
                        {copied ? (
                            <>
                                <Check className="h-4 w-4 mr-2 text-green-400" />
                                Copied!
                            </>
                        ) : (
                             <>
                                <Copy className="h-4 w-4 mr-2" />
                                Copy
                            </>
                        )}
                    </Button>
                </div>
            </div>
        ) : app.id === 'chatgpt' ? (
            <div className="px-4 py-2 text-center space-y-4">
                <div className="bg-amber-900/20 border border-amber-700/50 rounded-md p-3 mb-4">
                    <p className="text-amber-300 text-sm font-medium mb-1">⚠️ Admin Setup Required</p>
                    <p className="text-amber-200/80 text-xs">
                        A workspace admin needs to add this connector in ChatGPT settings.
                    </p>
                </div>
                <p className="text-zinc-400 text-sm mb-4">
                    Copy this MCP Server URL for your admin to add in ChatGPT workspace settings.
                </p>
                <div className="relative group bg-black border border-zinc-700 rounded-md p-3 font-mono text-xs text-zinc-300 flex items-center justify-between">
                    <code style={{ wordBreak: 'break-all' }}>{chatgptLink}</code>
                    <Button variant="ghost" className="ml-4 text-zinc-400 hover:text-white" onClick={() => handleCopy(chatgptLink)}>
                        {copied ? (
                            <>
                                <Check className="h-4 w-4 mr-2 text-green-400" />
                                Copied!
                            </>
                        ) : (
                             <>
                                <Copy className="h-4 w-4 mr-2" />
                                Copy
                            </>
                        )}
                    </Button>
                </div>
                <div className="text-left mt-4 space-y-2">
                    <p className="text-zinc-300 text-sm font-medium">For your admin:</p>
                    <ol className="text-zinc-400 text-xs space-y-1 ml-4">
                        <li>1. Go to ChatGPT workspace settings</li>
                        <li>2. Navigate to "Deep Research" or "Connectors"</li>
                        <li>3. Click "Add new connector"</li>
                        <li>4. Paste the MCP Server URL above</li>
                        <li>5. Set Authentication to "No authentication"</li>
                        <li>6. Save the connector</li>
                    </ol>
                </div>
            </div>
        ) : app.id === 'substack' || app.id === 'twitter' ? (
            <div className="px-4 py-2 space-y-4">
                <p className="text-zinc-300 text-center text-sm">
                    Enter your {app.name === 'X' ? 'username' : 'URL'} below. This allows Jean Memory to find and sync your content.
                </p>
                <div className="flex items-center gap-4">
                  <Input
                    type="text"
                    placeholder={app.id === 'twitter' ? '@username' : 'your.substack.com'}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    className="bg-zinc-950 border-zinc-800 text-zinc-300 placeholder:text-zinc-500 flex-grow"
                    disabled={isLoading}
                  />
                </div>
                <Button
                  onClick={handleSync}
                  disabled={isLoading || !inputValue}
                  className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-100 transition-all duration-300 mt-4"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    "Connect and Sync"
                  )}
                </Button>
            </div>
        ) : (
            <div className="space-y-6 px-4 py-2">
                <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center">
                        <Key className="h-5 w-5 text-zinc-400" />
                    </div>
                    <div>
                    <h3 className="font-semibold text-md text-white">1. Run Install Command</h3>
                    <p className="text-zinc-400 text-sm mb-3">
                        Open your terminal and paste this command:
                    </p>
                    <div className="relative group bg-black border border-zinc-700 rounded-md p-3 font-mono text-xs text-zinc-300 flex items-center justify-between">
                        <code style={{ wordBreak: 'break-all' }}>{installCommand}</code>
                        <Button variant="ghost" className="ml-4 text-zinc-400 hover:text-white" onClick={() => handleCopy(installCommand)}>
                           {copied ? (
                            <>
                                <Check className="h-4 w-4 mr-2 text-green-400" />
                                Copied!
                            </>
                        ) : (
                             <>
                                <Copy className="h-4 w-4 mr-2" />
                                Copy
                            </>
                        )}
                        </Button>
                    </div>
                    </div>
                </div>
                
                <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center">
                        <Shield className="h-5 w-5 text-zinc-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-md text-white">2. Restart {app.name}</h3>
                        <p className="text-zinc-400 text-sm">
                        After the command completes, restart the {app.name} application. Jean Memory will be active.
                        </p>
                    </div>
                </div>
            </div>
        )}
        
        <div className="mt-6 text-center">
            <Button 
                onClick={() => onOpenChange(false)}
                className="w-full sm:w-auto bg-white text-black hover:bg-zinc-200"
            >
                Done
            </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
} 