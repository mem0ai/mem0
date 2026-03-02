"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useState, useRef } from "react";
import { GoPlus } from "react-icons/go";
import { Loader2 } from "lucide-react";
import { useAppsApi } from "@/hooks/useAppsApi";
import { toast } from "sonner";

export function CreateAppDialog() {
  const { createApp, isLoading, fetchApps } = useAppsApi();
  const [open, setOpen] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  const handleCreateApp = async () => {
    const name = nameRef.current?.value || "";
    const description = descriptionRef.current?.value || "";

    if (!name.trim()) {
      toast.error("App name is required");
      return;
    }

    try {
      await createApp(name, description);
      toast.success("App created successfully");
      // Close the dialog
      setOpen(false);
      // Clear the form
      if (nameRef.current) {
        nameRef.current.value = "";
      }
      if (descriptionRef.current) {
        descriptionRef.current.value = "";
      }
      // Refetch apps to update the list
      setTimeout(async () => {
        await fetchApps();
      }, 500);
    } catch (error: any) {
      console.error(error);
      const errorMessage = error.response?.data?.detail || "Failed to create app";
      toast.error(errorMessage);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="bg-primary hover:bg-primary/90 text-white border-primary"
        >
          <GoPlus className="mr-1" />
          Create App
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[525px] bg-zinc-900 border-zinc-800">
        <DialogHeader>
          <DialogTitle>Create New App</DialogTitle>
          <DialogDescription>
            Add a new app to your OpenMemory instance
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="name">App Name*</Label>
            <Input
              ref={nameRef}
              id="name"
              placeholder="e.g., My Application"
              className="bg-zinc-950 border-zinc-800"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              ref={descriptionRef}
              id="description"
              placeholder="Brief description of your app (optional)"
              className="bg-zinc-950 border-zinc-800 min-h-[100px]"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={isLoading}
            onClick={handleCreateApp}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              "Create App"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
