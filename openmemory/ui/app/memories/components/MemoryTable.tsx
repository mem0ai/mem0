import {
  Edit,
  MoreHorizontal,
  Trash2,
  Pause,
  Archive,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/hooks/use-toast";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/store/store";
import SourceApp from "@/components/shared/source-app";
import { useRouter } from "next/navigation";
import Categories from "@/components/shared/categories";
import { useUI } from "@/hooks/useUI";
import { formatDate } from "@/lib/helpers";

export function MemoryTable() {
  const { toast } = useToast();
  const router = useRouter();
  const memories = useSelector((state: RootState) => state.memories.memories);

  const { deleteMemories, updateMemoryState, isLoading } = useMemoriesApi();

  const handleDeleteMemory = (id: string) => {
    deleteMemories([id]);
  };

  const { handleOpenUpdateMemoryDialog } = useUI();

  const handleEditMemory = (memory_id: string, memory_content: string) => {
    handleOpenUpdateMemoryDialog(memory_id, memory_content);
  };

  const handleUpdateMemoryState = async (id: string, newState: string) => {
    try {
      await updateMemoryState([id], newState);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update memory state",
        variant: "destructive",
      });
    }
  };

  const handleMemoryClick = (id: string) => {
    router.push(`/memory/${id}`);
  };

  return (
    <div className="space-y-4">
      {memories.map((memory) => (
        <div
          key={memory.id}
          className={`bg-card border border-border rounded-lg p-4 transition-all duration-300 hover:border-primary/50 hover:shadow-lg ${
            memory.state === "paused" || memory.state === "archived"
              ? "text-muted-foreground"
              : ""
          } ${isLoading ? "animate-pulse opacity-50" : ""}`}
        >
          <div className="flex justify-between items-start">
            <div className="flex-1 cursor-pointer" onClick={() => handleMemoryClick(memory.id)}>
              <p className="text-sm line-clamp-3">{memory.memory}</p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 flex-shrink-0 ml-4">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                 <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => {
                        const newState =
                          memory.state === "active" ? "paused" : "active";
                        handleUpdateMemoryState(memory.id, newState);
                      }}
                    >
                      {memory?.state === "active" ? (
                        <>
                          <Pause className="mr-2 h-4 w-4" />
                          Pause
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Resume
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => {
                        const newState =
                          memory.state === "active" ? "archived" : "active";
                        handleUpdateMemoryState(memory.id, newState);
                      }}
                    >
                      <Archive className="mr-2 h-4 w-4" />
                      {memory?.state !== "archived" ? (
                        <>Archive</>
                      ) : (
                        <>Unarchive</>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => handleEditMemory(memory.id, memory.memory)}
                    >
                      <Edit className="mr-2 h-4 w-4" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="cursor-pointer text-red-500 focus:text-red-500"
                      onClick={() => handleDeleteMemory(memory.id)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between text-xs text-muted-foreground mt-4 gap-2 sm:gap-4">
             <div className="flex flex-wrap items-center gap-1">
                  <Categories
                    categories={memory.categories}
                    isPaused={
                      memory.state === "paused" || memory.state === "archived"
                    }
                    concat={true}
                  />
                </div>
            <div className="flex items-center gap-4 flex-shrink-0">
              <SourceApp source={memory.app_name} />
              <span>{formatDate(memory.created_at)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
