import React, { useEffect } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useStats } from "@/hooks/useStats";
import Image from "next/image";
import { constants } from "@/components/shared/source-app";
const Stats = () => {
  const totalMemories = useSelector(
    (state: RootState) => state.profile.totalMemories
  );
  const totalApps = useSelector((state: RootState) => state.profile.totalApps);
  const apps = useSelector((state: RootState) => state.profile.apps).slice(
    0,
    4
  );
  const { fetchStats } = useStats();

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800">
      <div className="bg-zinc-800 border-b border-zinc-800 rounded-t-lg p-4">
        <div className="text-white text-xl font-semibold">Memories Stats</div>
      </div>
      <div className="space-y-3 p-4">
        <div>
          <p className="text-zinc-400">Total Memories</p>
          <h3 className="text-lg font-bold text-white">
            {totalMemories} Memories
          </h3>
        </div>
        <div>
          <p className="text-zinc-400">Total Apps Connected</p>
          <div className="flex flex-col items-start gap-1 mt-2">
            <div className="flex -space-x-2">
              {apps.map((app) => (
                <div
                  key={app.id}
                  className={`h-8 w-8 rounded-full bg-primary flex items-center justify-center text-xs`}
                >
                  <div>
                    <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                      <Image
                        src={
                          constants[app.name as keyof typeof constants]
                            ?.iconImage || ""
                        }
                        alt={
                          constants[app.name as keyof typeof constants]?.name
                        }
                        width={32}
                        height={32}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <h3 className="text-lg font-bold text-white">{totalApps} Apps</h3>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Stats;
