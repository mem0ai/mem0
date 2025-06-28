import { ArrowRight } from "lucide-react";
import Categories from "@/components/shared/categories";
import Link from "next/link";
import { constants } from "@/components/shared/source-app";
import Image from "next/image";

interface MemoryCardProps {
  id: string;
  content: string;
  created_at: string;
  metadata?: Record<string, any>;
  categories?: string[];
  access_count?: number;
  app_name: string;
  state: string;
}

export function MemoryCard({
  id,
  content,
  created_at,
  metadata,
  categories,
  access_count,
  app_name,
  state,
}: MemoryCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="p-3 sm:p-4">
        <div className="border-l-2 border-primary pl-3 sm:pl-4 mb-3 sm:mb-4">
          <p
            className={`text-sm sm:text-base ${state !== "active" ? "text-muted-foreground" : "text-foreground"}`}
          >
            {content}
          </p>
        </div>

        {metadata && Object.keys(metadata).length > 0 && (
          <div className="mb-3 sm:mb-4">
            <p className="text-xs text-muted-foreground uppercase mb-2">METADATA</p>
            <div className="bg-muted rounded p-2 sm:p-3 text-muted-foreground overflow-x-auto">
              <pre className="whitespace-pre-wrap text-xs font-mono min-w-0">
                {JSON.stringify(metadata, null, 2)}
              </pre>
            </div>
          </div>
        )}

        <div className="mb-2 sm:mb-3">
          <Categories
            categories={categories as any}
            isPaused={state !== "active"}
          />
        </div>

        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-xs sm:text-sm">
              {access_count ? (
                <span>
                  Accessed {access_count} times
                </span>
              ) : (
                new Date(created_at + "Z").toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "numeric",
                })
              )}
            </span>

            {state !== "active" && (
              <span className="inline-block px-2 sm:px-3 border border-yellow-600 text-yellow-600 font-semibold text-xs rounded-full bg-yellow-400/10 backdrop-blur-sm">
                {state === "paused" ? "Paused" : "Archived"}
              </span>
            )}
          </div>

          {!app_name && (
            <Link
              href={`/memory/${id}`}
              className="hover:cursor-pointer bg-muted hover:bg-accent flex items-center px-3 py-1.5 text-xs sm:text-sm rounded-lg text-foreground hover:text-foreground self-start sm:self-auto"
            >
              View Details
              <ArrowRight className="ml-2 h-3 w-3 sm:h-4 sm:w-4" />
            </Link>
          )}
          {app_name && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 bg-muted px-2 sm:px-3 py-1 rounded-lg">
                <span className="text-xs sm:text-sm text-muted-foreground">Created by:</span>
                <div className="w-4 h-4 sm:w-5 sm:h-5 rounded-full bg-muted flex items-center justify-center overflow-hidden">
                  <Image
                    src={
                      constants[app_name as keyof typeof constants]
                        ?.iconImage || ""
                    }
                    alt="Jean Memory"
                    width={20}
                    height={20}
                  />
                </div>
                <p className="text-xs sm:text-sm text-foreground font-semibold">
                  {constants[app_name as keyof typeof constants]?.name}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 