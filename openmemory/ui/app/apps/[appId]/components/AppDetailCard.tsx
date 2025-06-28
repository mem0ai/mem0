import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { PauseIcon, Loader2, PlayIcon, Download, Copy } from "lucide-react";
import { useAppsApi } from "@/hooks/useAppsApi";
import Image from "next/image";
import { useDispatch, useSelector } from "react-redux";
import { setAppDetails } from "@/store/appsSlice";
import { BiEdit } from "react-icons/bi";
import { constants } from "@/components/shared/source-app";
import { RootState } from "@/store/store";
import { toast } from "@/components/ui/use-toast";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/AuthContext";

const capitalize = (str: string) => {
  return str.charAt(0).toUpperCase() + str.slice(1);
};

const AppDetailCard = ({
  appId,
  selectedApp,
}: {
  appId: string;
  selectedApp: any;
}) => {
  const { updateAppDetails } = useAppsApi();
  const [isLoading, setIsLoading] = useState(false);
  const dispatch = useDispatch();
  const apps = useSelector((state: RootState) => state.apps.apps);
  const { user } = useAuth();
  const currentApp = apps.find((app: any) => app.id === appId);
  const appConfig = currentApp
    ? constants[currentApp.name as keyof typeof constants] || constants.default
    : constants.default;

  const handlePauseAccess = async () => {
    setIsLoading(true);
    try {
      await updateAppDetails(appId, {
        is_active: !selectedApp.details.is_active,
      });
      dispatch(
        setAppDetails({ appId, isActive: !selectedApp.details.is_active })
      );
    } catch (error) {
      console.error("Failed to toggle app pause state:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const buttonText = selectedApp.details.is_active
    ? "Pause Access"
    : "Unpause Access";

  const installCommand = currentApp?.name === 'chorus' 
    ? `-y mcp-remote https://jean-memory-api.onrender.com/mcp/chorus/sse/${user?.id}`
    : `npx install-mcp https://api.jeanmemory.com/mcp/${currentApp?.name}/sse/${user?.id} --client ${currentApp?.name}`;

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copied to clipboard!",
      description: "You can now run this command in your terminal.",
    });
  };

  const handleDownloadExtension = () => {
    // Open the DXT download endpoint - backend FastAPI route
    const backendUrl = process.env.NODE_ENV === 'development' 
      ? 'http://localhost:8765' 
      : 'https://jean-memory-api.onrender.com';
    window.open(`${backendUrl}/download/claude-extension`, '_blank');
    
    toast({
      title: "Download Started",
      description: "The Claude Desktop Extension is downloading. Double-click the file to install.",
    });
  };

  return (
    <div>
      <div className="bg-card border w-full sm:w-[320px] border-border rounded-xl mb-6">
        <div className="flex items-center gap-2 mb-4 bg-muted rounded-t-xl p-3">
          <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center overflow-hidden">
            <Image
              src={
                constants[appId as keyof typeof constants]?.iconImage || ""
              }
              alt="Jean Memory"
              width={24}
              height={24}
            />
          </div>
          <p className="text-sm font-semibold text-foreground">
            {constants[appId as keyof typeof constants]?.name}
          </p>
        </div>

        <div className="space-y-4 p-3">
          <div>
            <p className="text-xs text-muted-foreground">Access Status</p>
            <p
              className={`font-medium ${
                selectedApp.details.is_active
                  ? "text-emerald-500"
                  : "text-red-500"
              }`}
            >
              {capitalize(
                selectedApp.details.is_active ? "active" : "inactive"
              )}
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground">Total Memories Created</p>
            <p className="font-medium text-foreground">
              {selectedApp.details.total_memories_created} Memories
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground">Total Memories Accessed</p>
            <p className="font-medium text-foreground">
              {selectedApp.details.total_memories_accessed} Memories
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground">First Accessed</p>
            <p className="font-medium text-foreground">
              {selectedApp.details.first_accessed
                ? new Date(
                    selectedApp.details.first_accessed
                  ).toLocaleDateString("en-US", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "numeric",
                    minute: "numeric",
                  })
                : "Never"}
            </p>
          </div>

          <div>
            <p className="text-xs text-muted-foreground">Last Accessed</p>
            <p className="font-medium text-foreground">
              {selectedApp.details.last_accessed
                ? new Date(
                    selectedApp.details.last_accessed
                  ).toLocaleDateString("en-US", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "numeric",
                    minute: "numeric",
                  })
                : "Never"}
            </p>
          </div>

          <hr className="border-border" />

          {currentApp?.name?.toLowerCase() === 'claude' ? (
            <div>
              <p className="text-xs text-muted-foreground mb-2">Desktop Extension</p>
              <Button 
                onClick={handleDownloadExtension}
                className="w-full mb-2"
                variant="secondary"
                size="sm"
              >
                <Download className="mr-2 h-4 w-4" />
                Download Extension
              </Button>
              <p className="text-xs text-muted-foreground">
                One-click install for Claude Desktop
              </p>
              <details className="mt-2">
                <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                  Show manual install command
                </summary>
                <div className="flex items-center gap-2 mt-2">
                  <Input
                    readOnly
                    value={installCommand}
                    className="bg-background border-border text-xs truncate"
                  />
                  <Button size="icon" variant="ghost" onClick={() => handleCopy(installCommand)}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </details>
            </div>
          ) : (
            <div>
              <p className="text-xs text-muted-foreground mb-2">Install Command</p>
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={installCommand}
                  className="bg-background border-border text-xs truncate"
                />
                <Button size="icon" variant="ghost" onClick={() => handleCopy(installCommand)}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <Button
              onClick={handlePauseAccess}
              className="flex bg-transparent w-[170px] bg-muted border-border hover:bg-accent text-foreground"
              size="sm"
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : buttonText === "Pause Access" ? (
                <PauseIcon className="h-4 w-4" />
              ) : (
                <PlayIcon className="h-4 w-4" />
              )}
              {buttonText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AppDetailCard;
