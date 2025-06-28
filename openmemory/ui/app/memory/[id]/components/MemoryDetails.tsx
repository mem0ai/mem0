"use client";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { MemoryActions } from "./MemoryActions";
import { ArrowLeft, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { AccessLog } from "./AccessLog";
import Image from "next/image";
import Categories from "@/components/shared/categories";
import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { constants } from "@/components/shared/source-app";
import { RelatedMemories } from "./RelatedMemories";

interface MemoryDetailsProps {
  memory_id: string;
}

export function MemoryDetails({ memory_id }: MemoryDetailsProps) {
  const router = useRouter();
  const { fetchMemoryById, hasUpdates } = useMemoriesApi();
  const memory = useSelector(
    (state: RootState) => state.memories.selectedMemory
  );
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (memory?.id) {
      await navigator.clipboard.writeText(memory.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  useEffect(() => {
    fetchMemoryById(memory_id);
  }, []);

  return (
    <div className="container mx-auto py-6 px-4">
      <Button
        variant="ghost"
        className="mb-4 text-zinc-400 hover:text-white"
        onClick={() => router.back()}
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Memories
      </Button>
      <div className="flex flex-col lg:flex-row gap-4 w-full">
        <div className="rounded-lg lg:w-2/3 border h-fit pb-2 border-border bg-card overflow-hidden">
          <div className="">
            <div className="flex px-4 sm:px-6 py-3 justify-between items-center mb-4 sm:mb-6 bg-muted border-b border-border">
              <div className="flex items-center gap-2">
                <h1 className="font-semibold text-foreground text-sm sm:text-base">
                  Memory{" "}
                  <span className="ml-1 text-muted-foreground text-xs sm:text-sm font-normal">
                    #{memory?.id?.slice(0, 6)}
                  </span>
                </h1>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 text-muted-foreground hover:text-foreground -ml-[5px] mt-1"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </Button>
              </div>
              <MemoryActions
                memoryId={memory?.id || ""}
                memoryContent={memory?.text || ""}
                memoryState={memory?.state || ""}
              />
            </div>

            <div className="px-4 sm:px-6 pb-4">
              <div className="border-l-2 border-primary pl-3 sm:pl-4 mb-4 sm:mb-6">
                <p className="text-sm sm:text-base text-foreground">
                  {memory?.text}
                </p>
              </div>

              {/* Categories */}
              <div className="mb-3 sm:mb-4">
                <Categories
                  categories={memory?.categories || []}
                  isPaused={memory?.state !== "active"}
                />
              </div>

              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
                <div className="text-xs sm:text-sm text-muted-foreground">
                  {new Date(memory?.created_at || "").toLocaleDateString(
                    "en-US",
                    {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "numeric",
                    }
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 min-w-0 justify-end">
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 bg-muted px-2 sm:px-3 py-1 rounded-lg">
                        <span className="text-xs sm:text-sm text-muted-foreground">
                          Created by:
                        </span>
                        <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center overflow-hidden">
                          <Image
                            src={
                              constants[
                                memory?.app_name as keyof typeof constants
                              ]?.iconImage || ""
                            }
                            alt="Jean Memory"
                            width={16}
                            height={16}
                          />
                        </div>
                        <p className="text-xs sm:text-sm text-foreground font-semibold">
                          {
                            constants[
                              memory?.app_name as keyof typeof constants
                            ]?.name
                          }
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="lg:w-1/3 flex flex-col gap-4">
          <AccessLog memoryId={memory?.id || ""} />
          <RelatedMemories memoryId={memory?.id || ""} />
        </div>
      </div>
    </div>
  );
}
