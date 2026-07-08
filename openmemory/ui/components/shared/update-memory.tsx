"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useRef } from "react";
import { Loader2 } from "lucide-react";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { toast } from "sonner";
import { Textarea } from "@/components/ui/textarea";
import { usePathname } from "next/navigation";

interface UpdateMemoryProps {
  memoryId: string;
  memoryContent: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const UpdateMemory = ({
  memoryId,
  memoryContent,
  open,
  onOpenChange,
}: UpdateMemoryProps) => {
  const { updateMemory, isLoading, fetchMemories, fetchMemoryById } =
    useMemoriesApi();
  const textRef = useRef<HTMLTextAreaElement>(null);
  const pathname = usePathname();

  const handleUpdateMemory = async (text: string) => {
    try {
      await updateMemory(memoryId, text);
      toast.success("Memory updated successfully");
      onOpenChange(false);
      if (pathname.includes("memories")) {
        await fetchMemories();
      } else {
        await fetchMemoryById(memoryId);
      }
    } catch (error) {
      console.error(error);
      toast.error("Failed to update memory");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[525px] bg-zinc-900 border-zinc-800 z-50">
        <DialogHeader>
          <DialogTitle>Update Memory</DialogTitle>
          <DialogDescription>Edit your existing memory</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="memory">Memory</Label>
            <Textarea
              ref={textRef}
              id="memory"
              className="bg-zinc-950 border-zinc-800 min-h-[150px]"
              defaultValue={memoryContent}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            className="w-[140px]"
            disabled={isLoading}
            onClick={() => handleUpdateMemory(textRef?.current?.value || "")}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              "Update Memory"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default UpdateMemory;
