"use client";

import React, { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, CheckCircle, Loader2, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { getGlobalAccessToken } from '@/contexts/AuthContext';

interface MigrationStatus {
  isMigrated: boolean;
  isChecking: boolean;
  qdrantMemoryCount?: number;
  sqlMemoryCount?: number;
  error?: string;
}

async function checkQdrantMigrationStatus(): Promise<{ 
  isMigrated: boolean; 
  qdrantMemoryCount?: number;
  sqlMemoryCount?: number;
}> {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8765';
  const accessToken = getGlobalAccessToken();
  
  if (!accessToken) {
    throw new Error('No access token available');
  }
  
  try {
    const response = await fetch(`${API_URL}/api/v1/migration/status`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to check migration status: ${response.statusText}`);
    }

    const data = await response.json();
    
    return {
      isMigrated: data.is_migrated,
      qdrantMemoryCount: data.qdrant_memory_count,
      sqlMemoryCount: data.sql_memory_count,
    };
  } catch (error) {
    console.error('Error checking migration status:', error);
    throw error;
  }
}

export function MigrationBanner() {
  const { user } = useAuth();
  const [migrationStatus, setMigrationStatus] = useState<MigrationStatus>({
    isMigrated: false,
    isChecking: true,
  });

  useEffect(() => {
    async function checkStatus() {
      if (!user?.id) {
        setMigrationStatus({ isMigrated: false, isChecking: false });
        return;
      }

      setMigrationStatus({ isMigrated: false, isChecking: true });

      try {
        const status = await checkQdrantMigrationStatus();
        setMigrationStatus({
          isMigrated: status.isMigrated,
          isChecking: false,
          qdrantMemoryCount: status.qdrantMemoryCount,
          sqlMemoryCount: status.sqlMemoryCount,
        });
      } catch (error) {
        setMigrationStatus({
          isMigrated: false,
          isChecking: false,
          error: 'Failed to check migration status',
        });
      }
    }

    checkStatus();
  }, [user?.id]);

  if (migrationStatus.isChecking) {
    return (
      <Alert className="mb-6">
        <Loader2 className="h-4 w-4 animate-spin" />
        <AlertDescription>
          Checking migration status...
        </AlertDescription>
      </Alert>
    );
  }

  const handleDownloadExtension = () => {
    // Download the HTTP v2 extension (faster transport)
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'https://jean-memory-api-virginia.onrender.com';
    window.open(`${backendUrl}/download/claude-extension-http`, '_blank');
  };

  return (
    <Alert className={`mb-6 ${migrationStatus.isMigrated ? 'border-green-500' : 'border-yellow-500'}`}>
      <div className="flex items-start gap-3">
        {migrationStatus.isMigrated ? (
          <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
        ) : (
          <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
        )}
        <div className="flex-1">
          <AlertDescription className="text-sm">
            <p className="font-semibold mb-2">
              System Upgrade Notice - July 8, 2025
            </p>
            <p className="mb-3">
              We are currently migrating data and upgrading our memory system. Some features may experience temporary downtime.
            </p>
            
            {migrationStatus.isMigrated ? (
              <div className="space-y-3">
                <p className="text-green-700 dark:text-green-400 font-medium">
                  ✓ Your data has been successfully migrated!
                  {migrationStatus.qdrantMemoryCount && ` (${migrationStatus.qdrantMemoryCount.toLocaleString()} memories in Qdrant)`}
                </p>
                <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-md">
                  <p className="text-sm font-medium mb-2">
                    Action Required: Update Claude Desktop Extension
                  </p>
                  <p className="text-sm mb-3">
                    Please delete your current Jean Memory Claude Desktop extension and download the updated version.
                  </p>
                  <Button
                    size="sm"
                    onClick={handleDownloadExtension}
                    className="gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Download Jean Memory Extension
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-yellow-700 dark:text-yellow-400">
                Your data migration is pending. We'll notify you once your data has been migrated.
              </p>
            )}
          </AlertDescription>
        </div>
      </div>
    </Alert>
  );
}