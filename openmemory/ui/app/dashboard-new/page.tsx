"use client";

import { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { useAppsApi } from '@/hooks/useAppsApi';
import { RootState } from '@/store/store';
import { InstallModal } from '@/components/dashboard/InstallModal';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { usePostHog } from 'posthog-js/react';
import { ArrowRight } from 'lucide-react';
import { useMemoriesApi } from '@/hooks/useMemoriesApi';
import { AnalysisPanel } from '@/components/dashboard/AnalysisPanel';
import { AppCard, DashboardApp } from '@/components/dashboard/AppCard';
import { useToast } from "@/components/ui/use-toast";
import ParticleNetwork from "@/components/landing/ParticleNetwork";
import { SyncModal } from '@/components/dashboard/SyncModal';

// Define available apps with priorities
interface AvailableApp {
  id: string;
  name: string;
  description: string;
  priority: number;
  category: string;
  icon?: string;
  trustScore?: number;
  isComingSoon?: boolean;
}

const availableApps: AvailableApp[] = [
  { id: 'claude', name: 'Claude', description: 'AI assistant for conversations', priority: 11, category: 'AI Assistant', trustScore: 96 },
  { id: 'cursor', name: 'Cursor', description: 'AI-powered code editor', priority: 10, category: 'Development', trustScore: 98 },
  { id: 'substack', name: 'Substack', description: 'Newsletter and publishing platform', priority: 9, category: 'Content', trustScore: 95 },
  { id: 'twitter', name: 'X', description: 'Social media and microblogging', priority: 8, category: 'Social', trustScore: 93 },
  { id: 'obsidian', name: 'Obsidian', description: 'Powerful knowledge base application', priority: 7, category: 'Productivity', trustScore: 94, isComingSoon: true },
  { id: 'notion', name: 'Notion', description: 'Connected workspace for notes & projects', priority: 6, category: 'Productivity', trustScore: 92, isComingSoon: true },
  { id: 'windsurf', name: 'Windsurf', description: 'Collaborative development environment', priority: 5, category: 'Development', trustScore: 94 },
  { id: 'mcp-generic', name: 'MCP Link', description: 'Connect to any MCP-compatible app', priority: 4, category: 'Integration', trustScore: 91 },
  { id: 'cline', name: 'Cline', description: 'Command line interface tool', priority: 3, category: 'Development', trustScore: 92 },
  { id: 'roocode', name: 'RooCode', description: 'Code review and collaboration', priority: 2, category: 'Development', trustScore: 90 },
  { id: 'witsy', name: 'Witsy', description: 'Smart productivity assistant', priority: 1, category: 'Productivity', trustScore: 88 },
  { id: 'enconvo', name: 'Enconvo', description: 'Environment configuration tool', priority: 0, category: 'Development', trustScore: 86 },
];

const createAppFromTemplate = (template: AvailableApp): DashboardApp => ({
  id: template.id,
  name: template.name,
  total_memories_created: 0,
  total_memories_accessed: 0,
  is_active: false,
  description: template.description,
  category: template.category,
  priority: template.priority,
  trustScore: template.trustScore,
  is_connected: false,
  isComingSoon: template.isComingSoon,
});

export default function DashboardNew() {
  const { user } = useAuth();
  const { fetchApps, checkTaskStatus } = useAppsApi();
  const connectedAppsFromApi = useSelector((state: RootState) => state.apps.apps);
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
  const [selectedApp, setSelectedApp] = useState<DashboardApp | null>(null);
  const [mounted, setMounted] = useState(false);
  const [hasFetchedApps, setHasFetchedApps] = useState(false);
  const [showAllApps, setShowAllApps] = useState(false);
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const posthog = usePostHog();
  const { fetchMemories } = useMemoriesApi();
  const [totalMemories, setTotalMemories] = useState(0);
  const [syncingApps, setSyncingApps] = useState<Record<string, boolean>>({});
  const [appTaskIds, setAppTaskIds] = useState<Record<string, string | null>>({});
  const { toast } = useToast();

  const handleModalClose = (open: boolean) => {
    setIsInstallModalOpen(open);
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (user && !hasFetchedApps) {
      fetchApps();
      setHasFetchedApps(true);
    }
  }, [user, fetchApps, hasFetchedApps]);

  useEffect(() => {
    const getTotalMemories = async () => {
      try {
        const result = await fetchMemories('', 1, 1);
        setTotalMemories(result.total);
      } catch (error) {
        console.error("Failed to fetch total memories:", error);
      }
    };
    if (user) {
      getTotalMemories();
    }
  }, [user, fetchMemories]);

  // Polling logic for task status
  useEffect(() => {
    const activeTasks = Object.entries(appTaskIds).filter(([, taskId]) => taskId !== null);
    if (activeTasks.length === 0) return;

    const intervalId = setInterval(async () => {
      for (const [appId, taskId] of activeTasks) {
        if (!taskId) continue;

        const taskStatus = await checkTaskStatus(taskId);
        if (taskStatus && (taskStatus.status === 'completed' || taskStatus.status === 'failed')) {
          setSyncingApps(prev => ({ ...prev, [appId]: false }));
          setAppTaskIds(prev => ({ ...prev, [appId]: null }));
          
          const appName = availableApps.find(a => a.id === appId)?.name || 'The app';

          if (taskStatus.status === 'completed') {
            toast({
              title: "Sync Complete",
              description: `${appName} has finished syncing.`,
            });
            
            // FIXED: Mark the app as connected after successful sync
            // This updates the UI to show the app as connected
            // The next fetchApps() call will get the updated connection status from backend
          } else {
            toast({
              variant: "destructive",
              title: "Sync Failed",
              description: `Sync for ${appName} failed. ${taskStatus.error || 'Unknown error'}`,
            });
          }

          // Refresh data - this will update the connection status from backend
          fetchApps();
          const getTotalMemories = async () => {
            try {
              const result = await fetchMemories('', 1, 1);
              setTotalMemories(result.total);
            } catch (error) {
              console.error("Failed to fetch total memories:", error);
            }
          };
          getTotalMemories();
        }
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(intervalId);
  }, [appTaskIds, checkTaskStatus, fetchApps, toast, fetchMemories]);

  // 📊 Track dashboard visits
  useEffect(() => {
    if (posthog && user) {
      posthog.capture('dashboard_new_visited', {
        user_id: user.id,
        user_email: user.email
      });
    }
  }, [posthog, user]);

  if (!mounted) {
    return null;
  }

  // Create a map of connected apps by id for quick lookup
  const connectedAppsMap = new Map(
    connectedAppsFromApi.map(app => [app.id.toLowerCase(), app])
  );

  // Merge available apps with connected status
  const allApps = availableApps.map(template => {
    const connectedApp = connectedAppsMap.get(template.id.toLowerCase());
    if (connectedApp) {
      // Make sure all properties from the connected app are carried over
      const mergedApp = { ...createAppFromTemplate(template), ...connectedApp, is_connected: true };
      return mergedApp;
    }
    
    // FIXED: Also check if this app exists in the API response with memories (Twitter/Substack case)
    const hasApiConnection = connectedAppsFromApi.find(apiApp => {
      const nameMatch = apiApp.name?.toLowerCase() === template.id.toLowerCase();
      const hasMemories = apiApp.total_memories_created && apiApp.total_memories_created > 0;
      const isActive = apiApp.is_active !== false;
      return nameMatch && hasMemories && isActive;
    });
    
    if (hasApiConnection) {
      // Mark as connected and include the API data
      return {
        ...createAppFromTemplate(template),
        ...hasApiConnection,
        is_connected: true
      };
    }
    
    return createAppFromTemplate(template);
  });

  // Sort by priority (highest first)
  const sortedApps = allApps.sort((a, b) => (b.priority || 0) - (a.priority || 0));
  
  // FIXED: Count connected apps properly including Twitter/Substack that may have been created via sync
  const connectedCount = sortedApps.filter(app => {
    // Check if app is connected via API OR if it's Twitter/Substack with active syncing
    const isConnectedViaAPI = app.is_connected && !app.isComingSoon;
    const isActiveSyncing = syncingApps[app.id] || appTaskIds[app.id];
    
    // Check if this app exists in the backend API response and has created memories
    const hasApiConnection = connectedAppsFromApi.some(connectedApp => {
      const nameMatch = connectedApp.name?.toLowerCase() === app.id.toLowerCase();
      const hasMemories = connectedApp.total_memories_created && connectedApp.total_memories_created > 0;
      const isActive = connectedApp.is_active !== false; // Default to true if undefined
      return nameMatch && hasMemories && isActive;
    });
    
    return (isConnectedViaAPI || isActiveSyncing || hasApiConnection) && !app.isComingSoon;
  }).length;
  
  const displayedApps = showAllApps ? sortedApps : sortedApps.slice(0, 6);

  const handleConnectApp = (app: DashboardApp) => {
    if (app.is_connected || app.isComingSoon) return;

    // Twitter and Substack have their own connection flow within the AppCard
    if (app.id === 'twitter' || app.id === 'substack') {
      setSelectedApp(app);
      setIsSyncModalOpen(true);
      return;
    }
    
    setSelectedApp(app);
    setIsInstallModalOpen(true);
    
    // 📊 Track app connection attempts
    if (posthog && user) {
      posthog.capture('app_connect_attempted', {
        user_id: user.id,
        app_name: app.name,
        app_category: app.category
      });
    }
  };

  return (
    <div className="relative min-h-screen bg-background text-foreground">
      {/* Background Animation */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <ParticleNetwork id="dashboard-particles" className="h-full w-full" interactive={false} particleCount={80} />
      </div>

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-4 py-8 max-w-7xl">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Side */}
          <div className="lg:col-span-2">
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-8"
            >
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">
                Connect Your Universe
              </h1>
              <p className="mt-3 text-lg text-muted-foreground">
                A single, unified memory layer for all your AI applications.
              </p>
            </motion.div>

            {/* Connection Status */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="mb-8"
            >
              <div className="bg-card border border-border rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <p className="text-sm font-medium text-foreground">
                    {connectedCount} of {availableApps.filter(a => !a.isComingSoon).length} Apps Connected
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {totalMemories.toLocaleString()} Memories Created
                  </p>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <div 
                    className="bg-primary h-2 rounded-full" 
                    style={{ width: `${(connectedCount / availableApps.filter(a => !a.isComingSoon).length) * 100}%` }}
                  ></div>
                </div>
              </div>
            </motion.div>

            {/* App Grid */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {displayedApps.map((app, index) => (
                  <AppCard
                    key={app.id || index}
                    app={app}
                    onConnect={handleConnectApp}
                    index={index}
                    isSyncing={syncingApps[app.id] || !!appTaskIds[app.id]}
                    onSyncStart={(appId, taskId) => {
                      setSyncingApps(prev => ({ ...prev, [appId]: true }));
                      setAppTaskIds(prev => ({ ...prev, [appId]: taskId }));
                    }}
                  />
                ))}
              </div>
            </motion.div>
            
            {!showAllApps && sortedApps.length > 6 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="text-center mt-8"
              >
                <Button variant="ghost" onClick={() => setShowAllApps(true)}>
                  Show {sortedApps.length - 6} more apps <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </motion.div>
            )}
          </div>

          {/* Right Side */}
          <div className="lg:col-span-1">
            <AnalysisPanel />
          </div>
        </div>
      </div>
      
      {selectedApp && (
        <InstallModal
          open={isInstallModalOpen}
          onOpenChange={handleModalClose}
          app={selectedApp}
          onSyncStart={(appId, taskId) => {
            setSyncingApps(prev => ({ ...prev, [appId]: true }));
            setAppTaskIds(prev => ({ ...prev, [appId]: taskId }));
          }}
        />
      )}
      <SyncModal
        app={selectedApp}
        open={isSyncModalOpen}
        onOpenChange={setIsSyncModalOpen}
        onSyncStart={(appId, taskId) => {
          setSyncingApps(prev => ({ ...prev, [appId]: true }));
          setAppTaskIds(prev => ({ ...prev, [appId]: taskId }));
        }}
      />
    </div>
  );
} 