"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { RefreshCw, RotateCcw, Save, ToggleLeft, ToggleRight, Plus, Trash2 } from "lucide-react";

interface Prompt {
  id: string;
  prompt_type: string;
  display_name: string;
  description: string | null;
  content: string;
  is_active: boolean;
  version: number;
  metadata_: Record<string, any>;
  created_at: string;
  updated_at: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

export function PromptsView() {
  const { toast } = useToast();
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>("");
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null);
  const [editedContent, setEditedContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  // Create form state
  const [newPrompt, setNewPrompt] = useState({
    prompt_type: "",
    display_name: "",
    description: "",
    content: "",
    is_active: true,
  });

  // Load all prompts
  const loadPrompts = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/prompts/`);
      if (!response.ok) throw new Error("Failed to load prompts");

      const data = await response.json();
      setPrompts(data);

      // Auto-select first prompt if none selected
      if (data.length > 0 && !selectedPromptId) {
        setSelectedPromptId(data[0].id);
        setSelectedPrompt(data[0]);
        setEditedContent(data[0].content);
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load prompts",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, []);

  // Handle prompt selection
  const handlePromptSelect = (promptId: string) => {
    const prompt = prompts.find(p => p.id === promptId);
    if (prompt) {
      setSelectedPromptId(promptId);
      setSelectedPrompt(prompt);
      setEditedContent(prompt.content);
    }
  };

  // Create new prompt
  const handleCreate = async () => {
    if (!newPrompt.prompt_type || !newPrompt.display_name || !newPrompt.content) {
      toast({
        title: "Validation Error",
        description: "Prompt type, display name, and content are required",
        variant: "destructive",
      });
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/prompts/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newPrompt),
      });

      if (!response.ok) throw new Error("Failed to create prompt");

      const createdPrompt = await response.json();

      // Update local state
      setPrompts([...prompts, createdPrompt]);
      setSelectedPromptId(createdPrompt.id);
      setSelectedPrompt(createdPrompt);
      setEditedContent(createdPrompt.content);

      // Reset form
      setNewPrompt({
        prompt_type: "",
        display_name: "",
        description: "",
        content: "",
        is_active: true,
      });
      setIsCreateDialogOpen(false);

      toast({
        title: "Success",
        description: `Prompt "${createdPrompt.display_name}" created successfully`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create prompt",
        variant: "destructive",
      });
    }
  };

  // Save prompt
  const handleSave = async () => {
    if (!selectedPrompt) return;

    setIsSaving(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/prompts/${selectedPrompt.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: editedContent }),
        }
      );

      if (!response.ok) throw new Error("Failed to save prompt");

      const updatedPrompt = await response.json();

      // Update local state
      setPrompts(prompts.map(p =>
        p.id === updatedPrompt.id ? updatedPrompt : p
      ));
      setSelectedPrompt(updatedPrompt);

      toast({
        title: "Success",
        description: `Prompt "${updatedPrompt.display_name}" saved successfully`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save prompt",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Delete prompt
  const handleDelete = async () => {
    if (!selectedPrompt) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/prompts/${selectedPrompt.id}`,
        { method: "DELETE" }
      );

      if (!response.ok) throw new Error("Failed to delete prompt");

      // Update local state
      const updatedPrompts = prompts.filter(p => p.id !== selectedPrompt.id);
      setPrompts(updatedPrompts);

      // Select first remaining prompt
      if (updatedPrompts.length > 0) {
        setSelectedPromptId(updatedPrompts[0].id);
        setSelectedPrompt(updatedPrompts[0]);
        setEditedContent(updatedPrompts[0].content);
      } else {
        setSelectedPromptId("");
        setSelectedPrompt(null);
        setEditedContent("");
      }

      toast({
        title: "Success",
        description: `Prompt "${selectedPrompt.display_name}" deleted successfully`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete prompt",
        variant: "destructive",
      });
    }
  };

  // Reset prompt to default
  const handleReset = async () => {
    if (!selectedPrompt) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/prompts/${selectedPrompt.id}/reset`,
        { method: "POST" }
      );

      if (!response.ok) throw new Error("Failed to reset prompt");

      const resetPrompt = await response.json();

      // Update local state
      setPrompts(prompts.map(p =>
        p.id === resetPrompt.id ? resetPrompt : p
      ));
      setSelectedPrompt(resetPrompt);
      setEditedContent(resetPrompt.content);

      toast({
        title: "Success",
        description: `Prompt "${resetPrompt.display_name}" reset to default`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to reset prompt",
        variant: "destructive",
      });
    }
  };

  // Toggle prompt active status
  const handleToggle = async () => {
    if (!selectedPrompt) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/prompts/${selectedPrompt.id}/toggle`,
        { method: "PATCH" }
      );

      if (!response.ok) throw new Error("Failed to toggle prompt");

      const toggledPrompt = await response.json();

      // Update local state
      setPrompts(prompts.map(p =>
        p.id === toggledPrompt.id ? toggledPrompt : p
      ));
      setSelectedPrompt(toggledPrompt);

      toast({
        title: "Success",
        description: `Prompt "${toggledPrompt.display_name}" is now ${toggledPrompt.is_active ? "active" : "inactive"}`,
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to toggle prompt status",
        variant: "destructive",
      });
    }
  };

  const hasChanges = selectedPrompt && editedContent !== selectedPrompt.content;

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle>Prompt Management</CardTitle>
            <CardDescription>
              Configure prompts used by the memory system for fact extraction, categorization, and memory operations
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm" className="border-zinc-800">
                  <Plus className="h-4 w-4 mr-2" />
                  New Prompt
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create New Prompt</DialogTitle>
                  <DialogDescription>
                    Create a custom prompt or variant of an existing prompt type
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="new-prompt-type">Prompt Type</Label>
                    <Input
                      id="new-prompt-type"
                      placeholder="e.g., user_memory_extraction, custom_type"
                      value={newPrompt.prompt_type}
                      onChange={(e) => setNewPrompt({ ...newPrompt, prompt_type: e.target.value })}
                      className="bg-zinc-900 border-zinc-800"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new-display-name">Display Name</Label>
                    <Input
                      id="new-display-name"
                      placeholder="e.g., Custom Memory Extraction"
                      value={newPrompt.display_name}
                      onChange={(e) => setNewPrompt({ ...newPrompt, display_name: e.target.value })}
                      className="bg-zinc-900 border-zinc-800"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new-description">Description (Optional)</Label>
                    <Input
                      id="new-description"
                      placeholder="Brief description of what this prompt does"
                      value={newPrompt.description}
                      onChange={(e) => setNewPrompt({ ...newPrompt, description: e.target.value })}
                      className="bg-zinc-900 border-zinc-800"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="new-content">Prompt Content</Label>
                    <Textarea
                      id="new-content"
                      placeholder="Enter the prompt content..."
                      value={newPrompt.content}
                      onChange={(e) => setNewPrompt({ ...newPrompt, content: e.target.value })}
                      className="font-mono text-sm min-h-[300px] bg-zinc-900 border-zinc-800"
                    />
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="new-is-active"
                      checked={newPrompt.is_active}
                      onChange={(e) => setNewPrompt({ ...newPrompt, is_active: e.target.checked })}
                      className="h-4 w-4"
                    />
                    <Label htmlFor="new-is-active">Active</Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} className="border-zinc-800">
                    Cancel
                  </Button>
                  <Button onClick={handleCreate} className="bg-primary hover:bg-primary/90">
                    Create Prompt
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Button
              variant="outline"
              size="sm"
              onClick={loadPrompts}
              disabled={isLoading}
              className="border-zinc-800"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Prompt Selector */}
        <div className="space-y-2">
          <Label htmlFor="prompt-select">Select Prompt</Label>
          <Select value={selectedPromptId} onValueChange={handlePromptSelect}>
            <SelectTrigger id="prompt-select" className="bg-zinc-900 border-zinc-800">
              <SelectValue placeholder="Choose a prompt..." />
            </SelectTrigger>
            <SelectContent>
              {prompts.map((prompt) => (
                <SelectItem key={prompt.id} value={prompt.id}>
                  <div className="flex items-center gap-2">
                    <span>{prompt.display_name}</span>
                    <span className="text-xs text-muted-foreground">({prompt.prompt_type})</span>
                    {!prompt.is_active && (
                      <Badge variant="outline" className="text-xs">Inactive</Badge>
                    )}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedPrompt && (
          <>
            {/* Prompt Info */}
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-sm text-muted-foreground">{selectedPrompt.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={selectedPrompt.is_active ? "default" : "secondary"}>
                  {selectedPrompt.is_active ? "Active" : "Inactive"}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  v{selectedPrompt.version}
                </Badge>
              </div>
            </div>

            {/* Editor */}
            <div className="space-y-2">
              <Label htmlFor="prompt-content">Prompt Content</Label>
              <Textarea
                id="prompt-content"
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                className="font-mono text-sm min-h-[400px] bg-zinc-900 border-zinc-800"
                placeholder="Enter prompt content..."
              />
            </div>

            {/* Actions */}
            <div className="flex justify-between items-center">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleToggle}
                  className="border-zinc-800"
                >
                  {selectedPrompt.is_active ? (
                    <>
                      <ToggleRight className="mr-2 h-4 w-4" />
                      Deactivate
                    </>
                  ) : (
                    <>
                      <ToggleLeft className="mr-2 h-4 w-4" />
                      Activate
                    </>
                  )}
                </Button>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" className="border-zinc-800">
                      <RotateCcw className="mr-2 h-4 w-4" />
                      Reset to Default
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Reset Prompt?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will reset "{selectedPrompt.display_name}" to its default content.
                        Any custom changes will be lost.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleReset} className="bg-red-600 hover:bg-red-700">
                        Reset
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" className="border-zinc-800 text-red-500 hover:text-red-600">
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete Prompt?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete "{selectedPrompt.display_name}".
                        This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>

              <Button
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                className="bg-primary hover:bg-primary/90"
              >
                <Save className="mr-2 h-4 w-4" />
                {isSaving ? "Saving..." : "Save Changes"}
              </Button>
            </div>

            {hasChanges && (
              <p className="text-sm text-amber-500">
                You have unsaved changes
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
