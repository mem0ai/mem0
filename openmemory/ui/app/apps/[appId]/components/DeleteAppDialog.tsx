import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAppsApi } from "@/hooks/useAppsApi";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { removeApp } from "@/store/appsSlice";
import { useRouter } from "next/navigation";
import { Trash2, AlertTriangle } from "lucide-react";

interface DeleteAppDialogProps {
  isOpen: boolean;
  onClose: () => void;
  appId: string;
  appName: string;
  memoryCount: number;
}

export const DeleteAppDialog: React.FC<DeleteAppDialogProps> = ({
  isOpen,
  onClose,
  appId,
  appName,
  memoryCount,
}) => {
  const [action, setAction] = useState<'delete_memories' | 'move_memories'>('delete_memories');
  const [targetAppId, setTargetAppId] = useState<string>('');
  const [isDeleting, setIsDeleting] = useState(false);
  
  const { deleteApp } = useAppsApi();
  const dispatch = useDispatch();
  const router = useRouter();
  const apps = useSelector((state: RootState) => state.apps.apps);
  
  // Filter out the current app from the list of available target apps
  const availableApps = apps.filter(app => app.id !== appId);

  const handleDelete = async () => {
    if (action === 'move_memories' && !targetAppId) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteApp(
        appId,
        action,
        action === 'move_memories' ? targetAppId : undefined
      );
      
      // Remove the app from the Redux store
      dispatch(removeApp(appId));
      
      // Close the dialog
      onClose();
      
      // Navigate back to apps list
      router.push('/apps');
    } catch (error) {
      console.error('Failed to delete app:', error);
      // You might want to show an error toast here
    } finally {
      setIsDeleting(false);
    }
  };

  const handleClose = () => {
    if (!isDeleting) {
      setAction('delete_memories');
      setTargetAppId('');
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px] bg-zinc-900 border-zinc-800 text-white">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="h-5 w-5" />
            Delete App
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            You are about to delete <strong className="text-white">{appName}</strong>.
            This app has <strong className="text-white">{memoryCount} memories</strong>.
            What would you like to do with these memories?
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">
              Memory Action
            </label>
            <Select value={action} onValueChange={(value: 'delete_memories' | 'move_memories') => setAction(value)}>
              <SelectTrigger className="bg-zinc-800 border-zinc-700 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-800 border-zinc-700">
                <SelectItem value="delete_memories" className="text-white hover:bg-zinc-700">
                  Delete all memories
                </SelectItem>
                <SelectItem value="move_memories" className="text-white hover:bg-zinc-700">
                  Move memories to another app
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {action === 'move_memories' && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">
                Target App
              </label>
              <Select value={targetAppId} onValueChange={setTargetAppId}>
                <SelectTrigger className="bg-zinc-800 border-zinc-700 text-white">
                  <SelectValue placeholder="Select an app to move memories to" />
                </SelectTrigger>
                <SelectContent className="bg-zinc-800 border-zinc-700">
                  {availableApps.map((app) => (
                    <SelectItem key={app.id} value={app.id} className="text-white hover:bg-zinc-700">
                      {app.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {availableApps.length === 0 && (
                <p className="text-sm text-yellow-400">
                  No other apps available. You cannot move memories without another app.
                </p>
              )}
            </div>
          )}

          {action === 'delete_memories' && (
            <div className="p-3 bg-red-900/20 border border-red-800 rounded-lg">
              <p className="text-sm text-red-300">
                <strong>Warning:</strong> This will permanently delete all {memoryCount} memories 
                associated with this app. This action cannot be undone.
              </p>
            </div>
          )}

          {action === 'move_memories' && targetAppId && (
            <div className="p-3 bg-blue-900/20 border border-blue-800 rounded-lg">
              <p className="text-sm text-blue-300">
                All {memoryCount} memories will be moved to the selected app. 
                The app "{appName}" will be deleted.
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isDeleting}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            Cancel
          </Button>
          <Button
            onClick={handleDelete}
            disabled={isDeleting || (action === 'move_memories' && (!targetAppId || availableApps.length === 0))}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="h-4 w-4 mr-2" />
                Delete App
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
