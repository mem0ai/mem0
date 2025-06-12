"use client";

import React, { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Copy, Check, ChevronDown, Link2 } from "lucide-react";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import { SubstackIntegration } from "./SubstackIntegration";
import { TwitterIntegration } from "./TwitterIntegration";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// Main apps to show in the primary tabs
const mainApps = [
  { key: "mcp", label: "MCP Link", icon: "🔗", isSpecial: true },
  { key: "claude", label: "Claude", icon: "/images/claude.webp" },
  { key: "cursor", label: "Cursor", icon: "/images/cursor.png" },
  { key: "substack", label: "Substack", icon: "/images/substack.png", isIntegration: true },
  { key: "twitter", label: "Twitter/X", icon: "🐦", isIntegration: true },
  { key: "windsurf", label: "Windsurf", icon: "/images/windsurf.png" },
];

// Additional apps in the dropdown
const additionalApps = [
  { key: "cline", label: "Cline", icon: "/images/cline.png" },
  { key: "roocode", label: "Roo Code", icon: "/images/roocline.png" },
  { key: "witsy", label: "Witsy", icon: "/images/witsy.png" },
  { key: "enconvo", label: "Enconvo", icon: "/images/enconvo.png" },
];

const colorGradientMap: { [key: string]: string } = {
  mcp: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-purple-500/20 data-[state=active]:to-transparent data-[state=active]:border-purple-500",
  claude: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-orange-500/20 data-[state=active]:to-transparent data-[state=active]:border-orange-500",
  cursor: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-blue-500/20 data-[state=active]:to-transparent data-[state=active]:border-blue-500",
  substack: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-[#FF6719]/20 data-[state=active]:to-transparent data-[state=active]:border-[#FF6719]",
  twitter: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-[#1DA1F2]/20 data-[state=active]:to-transparent data-[state=active]:border-[#1DA1F2]",
  windsurf: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-teal-500/20 data-[state=active]:to-transparent data-[state=active]:border-teal-500",
  more: "data-[state=active]:bg-gradient-to-t data-[state=active]:from-zinc-500/20 data-[state=active]:to-transparent data-[state=active]:border-zinc-500",
};

const API_URL_ON_LOAD = 
  process.env.NEXT_PUBLIC_API_URL || 
  (process.env.NODE_ENV === 'production' 
    ? "https://jean-memory-api.onrender.com" 
    : "http://localhost:8765");

export const Install = () => {
  const [copiedTab, setCopiedTab] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("claude");
  const { user } = useAuth();
  
  const userId = user?.id || "user";
  const URL = API_URL_ON_LOAD;

  const handleCopy = async (tab: string, isMcp: boolean = false) => {
    const textToCopy =
      tab === 'openmemory'
        ? `${URL}/mcp/openmemory/sse/${userId}`
        : `npx install-mcp ${URL}/mcp/${tab}/sse/${userId} --client ${tab}`;

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = textToCopy;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }

      setCopiedTab(tab);
      setTimeout(() => setCopiedTab(null), 2000);
    } catch (error) {
      console.error("Failed to copy text:", error);
    }
  };

  const renderInstallCard = (appKey: string, title: string, isMcp: boolean = false) => (
    <Card className="bg-zinc-900/50 border-zinc-800 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-medium text-zinc-100">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative group">
          <pre className="bg-zinc-950/50 border border-zinc-800 px-4 py-3 rounded-lg overflow-x-auto text-sm font-mono">
            <code className="text-zinc-300">
              {isMcp 
                ? `${URL}/mcp/openmemory/sse/${userId}`
                : `npx install-mcp ${URL}/mcp/${appKey}/sse/${userId} --client ${appKey}`
              }
            </code>
          </pre>
          <button
            className="absolute top-2 right-2 p-2 rounded-md bg-zinc-800 hover:bg-zinc-700 transition-colors opacity-0 group-hover:opacity-100"
            aria-label="Copy to clipboard"
            onClick={() => handleCopy(appKey, isMcp)}
          >
            {copiedTab === appKey ? (
              <Check className="h-4 w-4 text-green-400" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400" />
            )}
          </button>
        </div>
        {isMcp && (
          <p className="text-xs text-zinc-500 mt-3">
            Use this URL to connect Jean Memory to any MCP-compatible application
          </p>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-100 mb-2">Quick Setup</h2>
        <p className="text-zinc-400 text-sm">
          Connect Jean Memory to your favorite AI tools in seconds
        </p>
      </div>
      
      {!user && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg backdrop-blur-sm">
          <p className="text-amber-200 text-sm flex items-center gap-2">
            <span className="text-amber-400">⚠️</span>
            Sign in to sync memories across all your devices
          </p>
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-transparent border-b border-zinc-800 rounded-none w-full justify-start gap-1 p-0 h-auto mobile-scroll-x scrollbar-hide">
          <div className="flex gap-1 min-w-max px-1 pb-0">
            {mainApps.map(({ key, label, icon }) => (
              <TabsTrigger
                key={key}
                value={key}
                className={`px-3 py-3 rounded-none flex-shrink-0 ${colorGradientMap[key] || ''} data-[state=active]:border-b-2 data-[state=active]:shadow-none text-zinc-400 data-[state=active]:text-white flex items-center gap-2 text-sm font-medium transition-all whitespace-nowrap min-w-fit`}
              >
                {icon.startsWith("/") ? (
                  <div className="w-4 h-4 rounded overflow-hidden bg-zinc-800 flex items-center justify-center">
                    <Image src={icon} alt={label} width={16} height={16} className="object-cover" />
                  </div>
                ) : key === "mcp" ? (
                  <Link2 className="w-4 h-4" />
                ) : (
                  <span className="text-sm">{icon}</span>
                )}
                <span className="text-sm">{label}</span>
              </TabsTrigger>
            ))}
            
            {/* More Apps Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className={`px-3 py-3 text-zinc-400 hover:text-white flex items-center gap-2 text-sm font-medium transition-all flex-shrink-0 whitespace-nowrap min-w-fit ${additionalApps.some(app => app.key === activeTab) ? 'text-white border-b-2 border-zinc-500' : ''}`}>
                  <ChevronDown className="w-4 h-4" />
                  <span className="text-sm">More Apps</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="bg-zinc-900 border-zinc-800">
                {additionalApps.map(({ key, label, icon }) => (
                  <DropdownMenuItem
                    key={key}
                    onClick={() => setActiveTab(key)}
                    className="flex items-center gap-2 cursor-pointer hover:bg-zinc-800"
                  >
                    {icon.startsWith("/") && (
                      <div className="w-5 h-5 rounded overflow-hidden bg-zinc-800 flex items-center justify-center">
                        <Image src={icon} alt={label} width={20} height={20} className="object-cover" />
                      </div>
                    )}
                    <span>{label}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </TabsList>

        {/* Main app contents */}
        {mainApps.map(({ key, label, isIntegration }) => (
          <TabsContent key={key} value={key} className="mt-6">
            {key === "substack" ? (
              <SubstackIntegration 
                onSyncComplete={(syncedCount) => {
                  console.log(`Successfully synced ${syncedCount} essays`);
                  // Optionally refresh any document counts or show a success message
                }}
              />
            ) : key === "twitter" ? (
              <TwitterIntegration />
            ) : (
              renderInstallCard(key, `${label} Installation`, key === "mcp")
            )}
          </TabsContent>
        ))}

        {/* Additional app contents */}
        {additionalApps.map(({ key, label }) => (
          <TabsContent key={key} value={key} className="mt-6">
            {renderInstallCard(key, `${label} Installation`)}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default Install;
