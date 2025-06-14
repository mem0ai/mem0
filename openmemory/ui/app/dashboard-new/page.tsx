"use client";

import { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { App } from '@/store/appsSlice';
import { useAppsApi } from '@/hooks/useAppsApi';
import { RootState } from '@/store/store';
import { InstallModal } from '@/components/dashboard/InstallModal';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { usePostHog } from 'posthog-js/react';
import { 
  CheckCircle, Brain, Sparkles, ArrowRight, 
  Plus, Check, Lock, Heart
} from 'lucide-react';
import { constants } from '@/components/shared/source-app';

// Extended App interface for dashboard with additional properties
interface DashboardApp extends App {
  description?: string;
  category?: string;
  priority?: number;
  trustScore?: number;
  is_connected?: boolean;
}

// Define available apps with priorities
interface AvailableApp {
  id: string;
  name: string;
  description: string;
  priority: number;
  category: string;
  icon?: string;
  trustScore?: number;
}

const availableApps: AvailableApp[] = [
  { id: 'cursor', name: 'Cursor', description: 'AI-powered code editor', priority: 5, category: 'Development', trustScore: 98 },
  { id: 'claude', name: 'Claude', description: 'AI assistant for conversations', priority: 4, category: 'AI Assistant', trustScore: 96 },
  { id: 'windsurf', name: 'Windsurf', description: 'Collaborative development environment', priority: 3, category: 'Development', trustScore: 94 },
  { id: 'cline', name: 'Cline', description: 'Command line interface tool', priority: 2, category: 'Development', trustScore: 92 },
  { id: 'roocode', name: 'RooCode', description: 'Code review and collaboration', priority: 1, category: 'Development', trustScore: 90 },
  { id: 'witsy', name: 'Witsy', description: 'Smart productivity assistant', priority: 1, category: 'Productivity', trustScore: 88 },
  { id: 'enconvo', name: 'Enconvo', description: 'Environment configuration tool', priority: 1, category: 'Development', trustScore: 86 },
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
});

export default function DashboardNew() {
  const { user } = useAuth();
  const { fetchApps } = useAppsApi();
  const connectedAppsFromApi = useSelector((state: RootState) => state.apps.apps);
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
  const [selectedApp, setSelectedApp] = useState<App | null>(null);
  const [mounted, setMounted] = useState(false);
  const [hasFetchedApps, setHasFetchedApps] = useState(false);
  const [showAllApps, setShowAllApps] = useState(false);
  const posthog = usePostHog();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (user && !hasFetchedApps) {
      fetchApps();
      setHasFetchedApps(true);
    }
  }, [user, fetchApps, hasFetchedApps]);

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
      return { ...connectedApp, priority: template.priority, trustScore: template.trustScore, is_connected: true };
    }
    return createAppFromTemplate(template);
  });

  // Sort by priority (highest first)
  const sortedApps = allApps.sort((a, b) => (b.priority || 0) - (a.priority || 0));
  const connectedCount = sortedApps.filter(app => app.is_connected).length;
  const displayedApps = showAllApps ? sortedApps : sortedApps.slice(0, 4);

  const handleConnectApp = (app: DashboardApp) => {
    if (app.is_connected) return;
    
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <div className="relative overflow-hidden bg-white/80 backdrop-blur-sm border-b border-gray-200/50">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-600/5 to-indigo-600/5" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="flex items-center justify-center mb-6"
            >
              <div className="p-3 bg-gradient-to-br from-pink-500 to-rose-500 rounded-2xl shadow-lg">
                <Brain className="w-8 h-8 text-white" />
              </div>
            </motion.div>
            
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4"
            >
              Help your AI remember you
            </motion.h1>
            
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto"
            >
              Connect your favorite AI tools to create a unified memory layer that grows with you
            </motion.p>

            {connectedCount > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="inline-flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full border border-green-200"
              >
                <Heart className="w-4 h-4 text-green-600" />
                <span className="font-medium">{connectedCount} app{connectedCount !== 1 ? 's' : ''} connected</span>
              </motion.div>
            )}
          </div>
        </div>
      </div>

      {/* Apps Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {displayedApps.map((app, index) => {
            const appConfig = constants[app.id as keyof typeof constants] || constants.default;
            
            return (
              <motion.div
                key={app.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="group"
              >
                <div className="relative bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-200/50 p-6 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 hover:-translate-y-1">
                  {/* App Icon & Name */}
                  <div className="flex items-center gap-4 mb-4">
                    <div className="relative">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center overflow-hidden shadow-sm">
                        {appConfig.iconImage ? (
                          <img
                            src={appConfig.iconImage}
                            alt={app.name}
                            className="w-8 h-8 object-cover"
                          />
                        ) : (
                          <div className="w-8 h-8 flex items-center justify-center text-gray-600">
                            {appConfig.icon}
                          </div>
                        )}
                      </div>
                      {app.is_connected && (
                        <div className="absolute -top-1 -right-1 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                          <Check className="w-3 h-3 text-white" />
                        </div>
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{app.name}</h3>
                      <p className="text-sm text-gray-500">{app.description}</p>
                    </div>
                  </div>

                  {/* Stats */}
                  {app.is_connected && (
                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Created</p>
                        <p className="font-semibold text-gray-900">{app.total_memories_created}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Accessed</p>
                        <p className="font-semibold text-gray-900">{app.total_memories_accessed}</p>
                      </div>
                    </div>
                  )}

                  {/* Action Button */}
                  <Button
                    onClick={() => handleConnectApp(app)}
                    disabled={app.is_connected}
                    className={`w-full ${
                      app.is_connected
                        ? 'bg-green-50 text-green-700 border-green-200 hover:bg-green-50'
                        : 'bg-blue-600 hover:bg-blue-700 text-white'
                    }`}
                    variant={app.is_connected ? "outline" : "default"}
                  >
                    {app.is_connected ? (
                      <>
                        <CheckCircle className="w-4 h-4 mr-2" />
                        Connected
                      </>
                    ) : (
                      <>
                        <Plus className="w-4 h-4 mr-2" />
                        Connect
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Show More Button */}
        {!showAllApps && sortedApps.length > 4 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="text-center mt-8"
          >
            <Button
              onClick={() => setShowAllApps(true)}
              variant="outline"
              className="bg-white/80 backdrop-blur-sm border-gray-200/50 hover:bg-white/90"
            >
              Show {sortedApps.length - 4} more apps
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </motion.div>
        )}

        {/* Trust Message */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="text-center mt-12"
        >
          <div className="inline-flex items-center gap-2 text-gray-500">
            <Lock className="w-4 h-4" />
            <span className="text-sm">Your data is yours forever</span>
          </div>
        </motion.div>
      </div>

      {/* Install Modal */}
      <InstallModal
        open={isInstallModalOpen}
        onOpenChange={setIsInstallModalOpen}
        app={selectedApp}
      />
    </div>
  );
} 