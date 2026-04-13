"use client";

import { Card, CardContent } from "@/components/ui/card";
import { useDashboardStats } from "@/hooks/useDashboardStats";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { formatCompactNumber } from "@/lib/utils";

export default function DashboardPage() {
  useDashboardStats();
  const stats = useSelector((state: RootState) => state.stats.stats);

  const cards = [
    { label: "Total Memories", value: stats.memory_count },
    { label: "Operations Today", value: stats.ops_today },
    { label: "Active API Keys", value: stats.active_api_keys },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.label} className="border-memBorder-primary">
            <CardContent className="p-5">
              <p className="text-xs text-onSurface-default-tertiary">
                {card.label}
              </p>
              <p className="text-2xl font-semibold mt-1">
                {formatCompactNumber(card.value)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
