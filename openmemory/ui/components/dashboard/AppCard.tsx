"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Link as LinkIcon, Eye, Zap, BookOpen } from "lucide-react";
import { App } from "@/store/appsSlice";
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from "@/components/ui/use-toast";
import { useAppConfig } from "@/hooks/useAppConfig";
import { useAppSync } from "@/hooks/useAppSync";

export interface DashboardApp extends App {
  description?: string;
  category?: string;
  is_connected?: boolean;
  priority?: number;
  trustScore?: number;
  isComingSoon?: boolean;
}

interface AppCardProps {
  app: DashboardApp;
  onConnect: (app: DashboardApp) => void;
  index: number;
  isSyncing: boolean;
  onSyncStart?: (appId: string, taskId: string) => void;
}

export function AppCard({ app, onConnect, index, isSyncing, onSyncStart }: AppCardProps) {
  const router = useRouter();
  const { user, accessToken } = useAuth();
  const { toast } = useToast();
  const [inputValue, setInputValue] = useState("");
  const appConfig = useAppConfig(app);
  const { isLoading, handleSync: performSync } = useAppSync({ app, onSyncStart });

  const handleNavigateToMemories = () => {
    router.push(`/apps/${app.id}`);
  };
  
  const handleSyncClick = async () => {
    const success = await performSync(inputValue);
    if (success) {
      setInputValue(""); // Clear input on successful sync start
    }
  };

  const isSpecialFlow = app.id === 'twitter' || app.id === 'substack';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 + index * 0.1 }}
      className="group h-full"
      onClick={() => {
        if (app.is_connected) {
          onConnect(app);
        }
      }}
    >
      <div className="relative bg-card rounded-lg border border-border p-4 h-full flex flex-col justify-between hover:border-primary/50 transition-all duration-300">
        {app.is_connected && (
            <div className="absolute top-2 right-2 text-xs text-muted-foreground">
                {(app.total_memories_created || 0).toLocaleString()}
            </div>
        )}
        <div>
          {/* App Icon & Name */}
          <div className="flex items-center gap-3 mb-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
                {appConfig.iconImage ? (
                  <img
                    src={appConfig.iconImage}
                    alt={app.name}
                    className={`w-6 h-6 object-cover ${app.id === 'twitter' ? 'dark:text-white' : ''}`}
                  />
                ) : (
                  <div className="w-6 h-6 flex items-center justify-center text-muted-foreground">
                    {appConfig.icon}
                  </div>
                )}
              </div>
              {app.is_connected && (
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 border-2 border-card rounded-full flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 text-white" />
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-foreground text-sm truncate">{app.name}</h3>
              {!app.isComingSoon && (
                <p className="text-xs text-muted-foreground truncate">{app.description}</p>
              )}
            </div>
          </div>

          {/* Special UI for connected apps OR for special connection flow */}
          {app.is_connected && isSpecialFlow && (
            <div className="mb-3 space-y-2">
                <div className="flex gap-1.5">
                    <Input 
                        type="text"
                        placeholder={app.id === 'twitter' ? '@username or URL' : 'username.substack.com'}
                        className="bg-background border-border text-xs h-8"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                    />
                    <Button onClick={handleSyncClick} disabled={isLoading} className="text-xs h-8 px-3">
                        {isLoading ? 'Syncing...' : 'Sync'}
                    </Button>
                </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          {!app.is_connected ? (
            <Button
              onClick={() => {
                onConnect(app);
              }}
              className="w-full text-xs h-8"
              variant="outline"
              disabled={app.isComingSoon || isSyncing}
            >
              {isSyncing ? (
                <>
                  <Zap className="w-3 h-3 mr-1.5 animate-pulse" />
                  Syncing...
                </>
              ) : app.isComingSoon ? (
                "Coming Soon"
              ) : (
                <>
                  <LinkIcon className="w-3 h-3 mr-1.5 group-hover:rotate-12 transition-transform" />
                  Connect
                </>
              )}
            </Button>
          ) : (
            <div className="w-full flex gap-1.5">
              {/* Connected Status */}
              <div className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded text-xs flex-1 ${
                  isSyncing 
                    ? 'bg-blue-500/10 border border-blue-500/20' 
                    : 'bg-green-500/10 border border-green-500/20'
              }`}>
                {isSyncing ? (
                  <>
                    <Zap className="w-3 h-3 text-blue-400 animate-pulse" />
                    <span className="text-blue-400">Syncing...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3 h-3 text-green-400" />
                    <span className="text-green-400">Connected</span>
                  </>
                )}
              </div>
              
              {/* View Memories Button */}
              <Button
                onClick={handleNavigateToMemories}
                className="text-xs h-7 px-2"
                variant="outline"
                size="sm"
              >
                <BookOpen className="w-3 h-3" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
} 