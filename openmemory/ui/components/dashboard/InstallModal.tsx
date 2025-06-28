"use client";

import React, { useState } from 'react';
import { App } from '@/store/appsSlice';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Copy, Check, Key, Shield, Link as LinkIcon, Loader2, CheckCircle, AlertCircle, MessageSquare, Info } from 'lucide-react';
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { constants } from "@/components/shared/source-app";
import Image from 'next/image';
import apiClient from '@/lib/apiClient';
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

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
  const [phoneNumber, setPhoneNumber] = useState('');
  const [hasConsented, setHasConsented] = useState(false);

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
  let commandParts = { command: '', args: '' };
  
  // Use direct backend URL for Chorus, Worker URL for others
  const MCP_URL = app.id === 'chorus' ? "https://jean-memory-api.onrender.com" : "https://api.jeanmemory.com";

  // Define a base command that can be used as a fallback, fixing the regression.
  let rawInstallCommand = app.installCommand;
  if (!rawInstallCommand) {
    if (app.id === 'chorus') {
      rawInstallCommand = `-y mcp-remote ${MCP_URL}/mcp/${app.id}/sse/{user_id}`;
    } else {
      rawInstallCommand = `npx install-mcp ${MCP_URL}/mcp/${app.id}/sse/{user_id} --client ${app.id}`;
    }
  }
  
  // Handle the special case for Chorus with a multi-part command
  if (app.id === 'chorus' && rawInstallCommand && rawInstallCommand.includes('#')) {
    const parts = rawInstallCommand.split('#');
    commandParts.command = parts[0];
    commandParts.args = parts[1].replace('{USER_ID}', user?.id || '');
  }
  
  const installCommand = rawInstallCommand
    .replace('{user_id}', user?.id || '')
    .replace('{USER_ID}', user?.id || '');
    
  const mcpLink = `${MCP_URL}/mcp/openmemory/sse/${user?.id}`;
  const chatgptLink = `${MCP_URL}/mcp/chatgpt/sse/${user?.id}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-card text-card-foreground border shadow-2xl shadow-blue-500/10">
        <DialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-muted border flex items-center justify-center mb-4">
            {app.id === 'sms' ? (
                <MessageSquare className="w-9 h-9 text-blue-400" />
            ) : app.imageUrl ? (
                <Image src={app.imageUrl} alt={app.name} width={36} height={36} />
            ) : appConfig.iconImage ? (
                <Image src={appConfig.iconImage} alt={app.name} width={36} height={36} />
            ) : (
                <div className="w-9 h-9 flex items-center justify-center">{appConfig.icon}</div>
            )}
          </div>
          <DialogTitle className="text-2xl font-bold">
            {app.id === 'mcp-generic' ? 'Your Universal MCP Link' : 
             app.id === 'chatgpt' ? 'Connect to ChatGPT Deep Research' :
             app.id === 'sms' ? 'Connect SMS to Jean Memory' :
             `Connect to ${app.name}`}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground pt-1">
            {app.id === 'mcp-generic'
                ? 'Use this URL for any MCP-compatible application.'
                : app.id === 'chatgpt'
                ? 'Add Jean Memory to ChatGPT Deep Research. Enterprise account required.'
                : app.id === 'substack' || app.id === 'twitter'
                ? `Provide your ${app.name} details to sync your content.`
                : app.id === 'sms'
                ? 'Add your phone number to interact with your memories via text message.'
                : `Activate Jean Memory for ${app.name} in two simple steps.`
            }
          </DialogDescription>
        </DialogHeader>

        {app.id === 'mcp-generic' ? (
            <div className="px-4 py-2 text-center">
                <p className="text-muted-foreground text-sm mb-4">
                    Copy this URL and paste it into any MCP-compatible application to connect it with Jean Memory.
                </p>
                <div className="relative group bg-background border rounded-md p-3 font-mono text-xs text-foreground flex items-center justify-between">
                    <code style={{ wordBreak: 'break-all' }}>{mcpLink}</code>
                    <Button variant="ghost" className="ml-4 text-muted-foreground hover:text-foreground" onClick={() => handleCopy(mcpLink)}>
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
                <p className="text-muted-foreground text-sm mb-4">
                    Copy this MCP Server URL for your admin to add in ChatGPT workspace settings.
                </p>
                <div className="relative group bg-background border rounded-md p-3 font-mono text-xs text-foreground flex items-center justify-between">
                    <code style={{ wordBreak: 'break-all' }}>{chatgptLink}</code>
                    <Button variant="ghost" className="ml-4 text-muted-foreground hover:text-foreground" onClick={() => handleCopy(chatgptLink)}>
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
                    <p className="text-foreground text-sm font-medium">For your admin:</p>
                    <ol className="text-muted-foreground text-xs space-y-1 ml-4">
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
                <p className="text-muted-foreground text-center text-sm">
                    Enter your {app.name === 'X' ? 'username' : 'URL'} below. This allows Jean Memory to find and sync your content.
                </p>
                <div className="flex items-center gap-4">
                  <Input
                    type="text"
                    placeholder={app.id === 'twitter' ? '@username' : 'your.substack.com'}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    className="bg-background"
                    disabled={isLoading}
                  />
                </div>
                <Button
                  onClick={handleSync}
                  disabled={isLoading || !inputValue}
                  className="w-full"
                  variant="secondary"
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
        ) : app.id === 'sms' ? (
            <div className="px-4 py-2 space-y-4 text-left">
              <div className="space-y-1">
                  <Label htmlFor="phone-number" className="text-sm font-medium text-foreground">Phone Number *</Label>
                  <Input
                    id="phone-number"
                    type="tel"
                    placeholder="(555) 123-4567"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="bg-background"
                  />
                  <p className="text-xs text-muted-foreground pt-1">US phone numbers only. Message & data rates may apply.</p>
              </div>

              <div className="bg-muted border rounded-lg p-3 text-sm mt-4">
                <div className="flex items-start">
                  <Info className="h-4 w-4 text-muted-foreground mt-0.5 mr-2 flex-shrink-0"/>
                  <div>
                    <p className="font-semibold text-foreground mb-2">How to Use Jean Memory SMS:</p>
                    <ul className="list-disc list-inside text-muted-foreground space-y-1 text-xs">
                        <li>Just text us naturally, like you're talking to a person!</li>
                        <li>"Remember to pick up groceries after work"</li>
                        <li>"What were the main points from the meeting yesterday?"</li>
                        <li>"Show my recent thoughts on the new project"</li>
                        <li>Text "help" anytime for more examples.</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="items-top flex space-x-3 pt-4">
                  <Checkbox
                      id="terms-sms"
                      checked={hasConsented}
                      onCheckedChange={(checked) => setHasConsented(checked as boolean)}
                      className="data-[state=checked]:bg-primary border-border mt-0.5"
                  />
                  <div className="grid gap-1.5 leading-none">
                      <label
                        htmlFor="terms-sms"
                        className="text-xs text-muted-foreground font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        I accept the <a href="/sms-terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-primary">SMS Terms of Service</a> & <a href="https://jonathan-politzki.github.io/jean-privacy-policy/" target="_blank" rel="noopener noreferrer" className="underline hover:text-primary">Privacy Policy</a>.
                      </label>
                  </div>
              </div>

              <p className="text-xs text-muted-foreground pt-3">
                By providing your phone number, you agree to receive informational text messages from Jean Memory. Consent is not a condition of purchase. Messages Frequency will vary. Msg & data rates may apply. Reply HELP for help or STOP to cancel.
              </p>

              <p className="text-center text-sm text-primary pt-2">
                Coming Soon: Full SMS integration is pending carrier approval.
              </p>
            </div>
        ) : app.id === 'chorus' ? (
          <div className="space-y-4 px-4 py-2">
            <ol className="list-decimal list-inside space-y-3 text-muted-foreground text-sm">
              <li>{app.modalContent}</li>
              <li>
                In the <code className="bg-muted px-1.5 py-0.5 rounded-md font-mono text-xs border">Command</code> field, enter: <code className="bg-muted px-1.5 py-0.5 rounded-md font-mono text-xs border">npx</code>
              </li>
              <li>
                In the <code className="bg-muted px-1.5 py-0.5 rounded-md font-mono text-xs border">Arguments</code> field, paste the following:
                <div className="relative mt-2">
                  <Input
                    id="chorus-args"
                    readOnly
                    value={installCommand}
                    className="bg-background border-border text-foreground font-mono text-xs pr-10"
                  />
                  <Button variant="ghost" size="icon" className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground hover:text-foreground" onClick={() => handleCopy(installCommand)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            </ol>
          </div>
        ) : (
            <div className="space-y-6 px-4 py-2">
                <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                        <Key className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div>
                    <h3 className="font-semibold text-md text-foreground">1. Run Install Command</h3>
                    <p className="text-muted-foreground text-sm mb-3">
                        Open your terminal and paste this command:
                    </p>
                    <div className="relative group bg-background border rounded-md p-3 font-mono text-xs text-foreground flex items-center justify-between">
                        <code style={{ wordBreak: 'break-all' }}>{installCommand}</code>
                        <Button variant="ghost" className="ml-4 text-muted-foreground hover:text-foreground" onClick={() => handleCopy(installCommand)}>
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
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                        <Shield className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-md text-foreground">2. Restart {app.name}</h3>
                        <p className="text-muted-foreground text-sm">
                        After the command completes, restart the {app.name} application. Jean Memory will be active.
                        </p>
                    </div>
                </div>
            </div>
        )}
        
        {app.id === 'sms' ? (
            <div className="mt-6 flex justify-end gap-3 px-4">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                    Cancel
                </Button>
                <Button
                  onClick={() => {
                      toast({
                          title: "Verification Sent (Mockup)",
                          description: "This demonstrates the user action to the review team.",
                      });
                  }}
                  disabled={!phoneNumber || !hasConsented}
                  variant="secondary"
                  >
                  Send Code
              </Button>
            </div>
        ) : (
          <div className="mt-6 text-center">
              <Button
                  variant="secondary"
                  onClick={() => onOpenChange(false)}
                  className="w-full sm:w-auto"
              >
                  Done
              </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
} 