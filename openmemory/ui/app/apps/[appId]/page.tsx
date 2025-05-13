"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useAppsApi } from "@/hooks/useAppsApi";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MemoryCard } from "./components/MemoryCard";
import AppDetailCard from "./components/AppDetailCard";
import "@/styles/animation.css";
import NotFound from "@/app/not-found";
import { AppDetailCardSkeleton } from "@/skeleton/AppDetailCardSkeleton";
import { MemoryCardSkeleton } from "@/skeleton/MemoryCardSkeleton";

export default function AppDetailsPage() {
  const params = useParams();
  const appId = params.appId as string;
  const [activeTab, setActiveTab] = useState("created");

  const {
    fetchAppDetails,
    fetchAppMemories,
    fetchAppAccessedMemories,
    fetchApps,
  } = useAppsApi();
  const selectedApp = useSelector((state: RootState) => state.apps.selectedApp);

  useEffect(() => {
    fetchApps({});
  }, [fetchApps]);

  useEffect(() => {
    const loadData = async () => {
      if (appId) {
        try {
          // Load all data in parallel
          await Promise.all([
            fetchAppDetails(appId),
            fetchAppMemories(appId),
            fetchAppAccessedMemories(appId),
          ]);
        } catch (error) {
          console.error("Error loading app data:", error);
        }
      }
    };

    loadData();
  }, [appId, fetchAppDetails, fetchAppMemories, fetchAppAccessedMemories]);

  if (selectedApp.error) {
    return (
      <NotFound message={selectedApp.error} title="Error loading app details" />
    );
  }

  if (!selectedApp.details) {
    return (
      <div className="flex-1 py-6 text-white">
        <div className="container flex justify-between">
          <div className="flex-1 p-4 max-w-4xl animate-fade-slide-down">
            <div className="mb-6">
              <div className="h-10 w-64 bg-zinc-800 rounded animate-pulse mb-6" />
              <div className="space-y-6">
                {[...Array(3)].map((_, i) => (
                  <MemoryCardSkeleton key={i} />
                ))}
              </div>
            </div>
          </div>
          <div className="p-14 animate-fade-slide-down delay-2">
            <AppDetailCardSkeleton />
          </div>
        </div>
      </div>
    );
  }

  const renderCreatedMemories = () => {
    const memories = selectedApp.memories.created;

    if (memories.loading) {
      return (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <MemoryCardSkeleton key={i} />
          ))}
        </div>
      );
    }

    if (memories.error) {
      return (
        <NotFound message={memories.error} title="Error loading memories" />
      );
    }

    if (memories.items.length === 0) {
      return (
        <div className="text-zinc-400 text-center py-8">No memories found</div>
      );
    }

    return memories.items.map((memory) => (
      <MemoryCard
        key={memory.id + memory.created_at}
        id={memory.id}
        content={memory.content}
        created_at={memory.created_at}
        metadata={memory.metadata_}
        categories={memory.categories}
        app_name={memory.app_name}
        state={memory.state}
      />
    ));
  };

  const renderAccessedMemories = () => {
    const memories = selectedApp.memories.accessed;

    if (memories.loading) {
      return (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <MemoryCardSkeleton key={i} />
          ))}
        </div>
      );
    }

    if (memories.error) {
      return (
        <div className="text-red-400 bg-red-400/10 p-4 rounded-lg">
          Error loading memories: {memories.error}
        </div>
      );
    }

    if (memories.items.length === 0) {
      return (
        <div className="text-zinc-400 text-center py-8">
          No accessed memories found
        </div>
      );
    }

    return memories.items.map((accessedMemory) => (
      <div
        key={accessedMemory.memory.id + accessedMemory.memory.created_at}
        className="relative"
      >
        <MemoryCard
          id={accessedMemory.memory.id}
          content={accessedMemory.memory.content}
          created_at={accessedMemory.memory.created_at}
          metadata={accessedMemory.memory.metadata_}
          categories={accessedMemory.memory.categories}
          access_count={accessedMemory.access_count}
          app_name={accessedMemory.memory.app_name}
          state={accessedMemory.memory.state}
        />
      </div>
    ));
  };

  return (
    <div className="flex-1 py-6 text-white">
      <div className="container flex justify-between">
        {/* Main content area */}
        <div className="flex-1 p-4 max-w-4xl animate-fade-slide-down">
          <Tabs
            defaultValue="created"
            className="mb-6"
            onValueChange={setActiveTab}
          >
            <TabsList className="bg-transparent border-b border-zinc-800 rounded-none w-full justify-start gap-8 p-0">
              <TabsTrigger
                value="created"
                className={`px-0 pb-2 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none ${
                  activeTab === "created" ? "text-white" : "text-zinc-400"
                }`}
              >
                Created ({selectedApp.memories.created.total})
              </TabsTrigger>
              <TabsTrigger
                value="accessed"
                className={`px-0 pb-2 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none ${
                  activeTab === "accessed" ? "text-white" : "text-zinc-400"
                }`}
              >
                Accessed ({selectedApp.memories.accessed.total})
              </TabsTrigger>
            </TabsList>

            <TabsContent
              value="created"
              className="mt-6 space-y-6 animate-fade-slide-down delay-1"
            >
              {renderCreatedMemories()}
            </TabsContent>

            <TabsContent
              value="accessed"
              className="mt-6 space-y-6 animate-fade-slide-down delay-1"
            >
              {renderAccessedMemories()}
            </TabsContent>
          </Tabs>
        </div>

        {/* Sidebar */}
        <div className="p-14 animate-fade-slide-down delay-2">
          <AppDetailCard appId={appId} selectedApp={selectedApp} />
        </div>
      </div>
    </div>
  );
}
