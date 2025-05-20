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
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
      <div className="p-4">
        <div className="border-l-2 border-primary pl-4 mb-4">
          <p
            className={`${state !== "active" ? "text-zinc-400" : "text-white"}`}
          >
            {content}
          </p>
        </div>

        {metadata && Object.keys(metadata).length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-zinc-500 uppercase mb-2">METADATA</p>
            <div className="bg-zinc-800 rounded p-3 text-zinc-400">
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(metadata, null, 2)}
              </pre>
            </div>
          </div>
        )}

        <div className="mb-2">
          <Categories
            categories={categories as any}
            isPaused={state !== "active"}
          />
        </div>

        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 text-sm">
              {access_count ? (
                <span className="relative top-1">
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
              <span className="inline-block px-3 border border-yellow-600 text-yellow-600 font-semibold text-xs rounded-full bg-yellow-400/10 backdrop-blur-sm">
                {state === "paused" ? "Paused" : "Archived"}
              </span>
            )}
          </div>

          {!app_name && (
            <Link
              href={`/memory/${id}`}
              className="hover:cursor-pointer bg-zinc-800 hover:bg-zinc-700 flex items-center px-3 py-1 text-sm rounded-lg text-white p-0 hover:text-white"
            >
              View Details
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          )}
          {app_name && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 bg-zinc-700 px-3 py-1 rounded-lg">
                <span className="text-sm text-zinc-400">Created by:</span>
                <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                  <Image
                    src={
                      constants[app_name as keyof typeof constants]
                        ?.iconImage || ""
                    }
                    alt="OpenMemory"
                    width={24}
                    height={24}
                  />
                </div>
                <p className="text-sm text-zinc-100 font-semibold">
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
