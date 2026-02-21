import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, UserCog } from "lucide-react";
import { toast } from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TransferOwnershipDialogProps {
  isOpen: boolean;
  onClose: () => void;
  appId: string;
  appName: string;
  currentOwner: string;
  onSuccess?: () => void;
}

interface User {
  id: string;
  user_id: string;
  name: string;
  email: string;
}

export const TransferOwnershipDialog: React.FC<TransferOwnershipDialogProps> = ({
  isOpen,
  onClose,
  appId,
  appName,
  currentOwner,
  onSuccess,
}) => {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";
  const [isLoading, setIsLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [customUserId, setCustomUserId] = useState<string>("");
  const [useCustomUser, setUseCustomUser] = useState(false);

  // Fetch users when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchUsers();
    }
  }, [isOpen]);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/apps/users`);
      if (!response.ok) throw new Error("Failed to fetch users");
      const data = await response.json();
      setUsers(data.users || []);
    } catch (error) {
      console.error("Error fetching users:", error);
      toast.error("Failed to load users");
    }
  };

  const handleTransfer = async () => {
    const newOwnerUserId = useCustomUser ? customUserId : selectedUserId;

    if (!newOwnerUserId) {
      toast.error("Please select or enter a user ID");
      return;
    }

    if (newOwnerUserId === currentOwner) {
      toast.error("This user already owns the app");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/v1/apps/${appId}/transfer-ownership`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          new_owner_user_id: newOwnerUserId,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to transfer ownership");
      }

      const result = await response.json();
      toast.success(
        `Successfully transferred "${appName}" from ${result.old_owner} to ${result.new_owner}`
      );
      onSuccess?.();
      onClose();
    } catch (error: any) {
      console.error("Error transferring ownership:", error);
      toast.error(error.message || "Failed to transfer ownership");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px] bg-zinc-900 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserCog className="h-5 w-5" />
            Transfer App Ownership
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Transfer ownership of <span className="font-semibold text-white">{appName}</span> to another user.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div>
            <Label className="text-sm text-zinc-400">Current Owner</Label>
            <div className="mt-1 px-3 py-2 bg-zinc-800 rounded-md text-sm">
              {currentOwner}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="customUser"
                checked={useCustomUser}
                onChange={(e) => setUseCustomUser(e.target.checked)}
                className="rounded border-zinc-700"
              />
              <Label htmlFor="customUser" className="text-sm text-zinc-400 cursor-pointer">
                Create new user
              </Label>
            </div>

            {useCustomUser ? (
              <div>
                <Label htmlFor="customUserId" className="text-sm text-zinc-400">
                  New User ID
                </Label>
                <Input
                  id="customUserId"
                  placeholder="Enter new user ID (e.g., stu)"
                  value={customUserId}
                  onChange={(e) => setCustomUserId(e.target.value)}
                  className="bg-zinc-800 border-zinc-700 mt-1"
                />
              </div>
            ) : (
              <div>
                <Label htmlFor="userId" className="text-sm text-zinc-400">
                  Select New Owner
                </Label>
                <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                  <SelectTrigger className="bg-zinc-800 border-zinc-700 mt-1">
                    <SelectValue placeholder="Select a user..." />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    {users
                      .filter((user) => user.user_id !== currentOwner)
                      .map((user) => (
                        <SelectItem key={user.id} value={user.user_id}>
                          {user.name || user.user_id} ({user.user_id})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex gap-2">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
            className="bg-transparent border-zinc-700 hover:bg-zinc-800"
          >
            Cancel
          </Button>
          <Button
            onClick={handleTransfer}
            disabled={isLoading || (!useCustomUser && !selectedUserId) || (useCustomUser && !customUserId)}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Transferring...
              </>
            ) : (
              <>
                <UserCog className="h-4 w-4 mr-2" />
                Transfer Ownership
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
