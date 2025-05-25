import React, { useEffect } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useStats } from "@/hooks/useStats";
import Image from "next/image";
import { constants } from "@/components/shared/source-app";
import { Brain, Layers } from "lucide-react";

const Stats = () => {
  const totalMemories = useSelector(
    (state: RootState) => state.profile.totalMemories
  );
  const totalApps = useSelector((state: RootState) => state.profile.totalApps);
  const apps = useSelector((state: RootState) => state.profile.apps).slice(
    0,
    3
  );
  const { fetchStats } = useStats();

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 backdrop-blur-sm">
      <div className="p-6">
        <h3 className="text-lg font-semibold text-zinc-100 mb-6">Overview</h3>
        
        {/* Memories Count */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Brain className="w-5 h-5 text-purple-400" />
            </div>
            <p className="text-zinc-400 text-sm">Total Memories</p>
          </div>
          <p className="text-2xl font-bold text-white ml-11">
            {totalMemories || 0}
          </p>
        </div>

        {/* Connected Apps */}
        <div>
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Layers className="w-5 h-5 text-blue-400" />
            </div>
            <p className="text-zinc-400 text-sm">Connected Apps</p>
          </div>
          
          {totalApps > 0 ? (
            <>
              <div className="flex items-center gap-2 ml-11 mb-2">
                <div className="flex -space-x-2">
                  {apps.map((app) => (
                    <div
                      key={app.id}
                      className="w-8 h-8 rounded-full bg-zinc-800 border-2 border-zinc-900 flex items-center justify-center overflow-hidden"
                    >
                      <Image
                        src={
                          constants[app.name as keyof typeof constants]
                            ?.iconImage || "/images/default-app.png"
                        }
                        alt={app.name}
                        width={24}
                        height={24}
                        className="object-cover"
                      />
                    </div>
                  ))}
                  {totalApps > 3 && (
                    <div className="w-8 h-8 rounded-full bg-zinc-800 border-2 border-zinc-900 flex items-center justify-center">
                      <span className="text-xs text-zinc-400">+{totalApps - 3}</span>
                    </div>
                  )}
                </div>
              </div>
              <p className="text-2xl font-bold text-white ml-11">
                {totalApps}
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-500 ml-11">
              No apps connected yet
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Stats;
