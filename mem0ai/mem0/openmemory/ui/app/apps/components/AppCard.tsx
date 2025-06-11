import type React from "react";
import { ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";

import { constants } from "@/components/shared/source-app";
import { App } from "@/store/appsSlice";
import Image from "next/image";
import { useRouter } from "next/navigation";

interface AppCardProps {
  app: App;
}

export function AppCard({ app }: AppCardProps) {
  const router = useRouter();
  const appConfig =
    constants[app.name as keyof typeof constants] || constants.default;
  const isActive = app.is_active;

  return (
    <Card className="bg-zinc-900 text-white border-zinc-800">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-1">
          <div className="relative z-10 rounded-full overflow-hidden bg-[#2a2a2a] w-6 h-6 flex items-center justify-center flex-shrink-0">
            {appConfig.iconImage ? (
              <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                <Image
                  src={appConfig.iconImage}
                  alt={appConfig.name}
                  width={28}
                  height={28}
                />
              </div>
            ) : (
              <div className="w-6 h-6 flex items-center justify-center">
                {appConfig.icon}
              </div>
            )}
          </div>
          <h2 className="text-xl font-semibold">{appConfig.name}</h2>
        </div>
      </CardHeader>
      <CardContent className="pb-4 my-1">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-zinc-400 text-sm mb-1">Memories Created</p>
            <p className="text-xl font-medium">
              {app.total_memories_created.toLocaleString()} Memories
            </p>
          </div>
          <div>
            <p className="text-zinc-400 text-sm mb-1">Memories Accessed</p>
            <p className="text-xl font-medium">
              {app.total_memories_accessed.toLocaleString()} Memories
            </p>
          </div>
        </div>
      </CardContent>
      <CardFooter className="border-t border-zinc-800 p-0 px-6 py-2 flex justify-between items-center">
        <div
          className={`${
            isActive
              ? "bg-green-800 text-white hover:bg-green-500/20"
              : "bg-red-500/20 text-red-400 hover:bg-red-500/20"
          } rounded-lg px-2 py-0.5 flex items-center text-sm`}
        >
          <span className="h-2 w-2 my-auto mr-1 rounded-full inline-block bg-current"></span>
          {isActive ? "Active" : "Inactive"}
        </div>
        <div
          onClick={() => router.push(`/apps/${app.id}`)}
          className="border hover:cursor-pointer border-zinc-700 bg-zinc-950 flex items-center px-3 py-1 text-sm rounded-lg text-white p-0 hover:bg-zinc-950/50 hover:text-white"
        >
          View Details <ArrowRight className="ml-2 h-4 w-4" />
        </div>
      </CardFooter>
    </Card>
  );
}
