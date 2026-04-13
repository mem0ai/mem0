"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { formatCompactNumber } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface RotatingMetricCardProps {
  icon: LucideIcon;
  iconColor: string;
  primaryMetric: {
    label: string;
    value: number;
  };
  secondaryMetric: {
    label: string;
    value: number;
  };
  rotationInterval?: number; // in milliseconds
}

export function RotatingMetricCard({
  icon: Icon,
  iconColor,
  primaryMetric,
  secondaryMetric,
  rotationInterval = 5000,
}: RotatingMetricCardProps) {
  const [showPrimary, setShowPrimary] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setShowPrimary((prev) => !prev);
    }, rotationInterval);

    return () => clearInterval(interval);
  }, [rotationInterval]);

  const currentMetric = showPrimary ? primaryMetric : secondaryMetric;

  return (
    <Card className="border-[#e9eaeb] rounded-md w-64 min-w-64">
      <CardContent className="flex items-center justify-between px-3 py-2 overflow-hidden">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Icon className={`size-4 shrink-0 ${iconColor}`} />
          <div className="relative min-w-0 h-5 flex items-center">
            <div
              className={`absolute w-full transition-all duration-500 ease-in-out ${
                showPrimary
                  ? "translate-y-0 opacity-100"
                  : "-translate-y-full opacity-0"
              }`}
            >
              <span className="text-[#717680] text-sm font-medium truncate">
                {primaryMetric.label}
              </span>
            </div>
            <div
              className={`absolute w-full transition-all duration-500 ease-in-out ${
                !showPrimary
                  ? "translate-y-0 opacity-100"
                  : "translate-y-full opacity-0"
              }`}
            >
              <span className="text-[#717680] text-sm font-medium truncate">
                {secondaryMetric.label}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center shrink-0">
          <div className="relative h-6 min-w-12 flex items-center justify-end">
            <div
              className={`absolute w-full flex items-center justify-end transition-all duration-500 ease-in-out ${
                showPrimary
                  ? "translate-y-0 opacity-100"
                  : "-translate-y-full opacity-0"
              }`}
            >
              <span className="text-[#181d27] dark:text-zinc-200 text-md font-semibold">
                {formatCompactNumber(primaryMetric.value)}
              </span>
            </div>
            <div
              className={`absolute w-full flex items-center justify-end transition-all duration-500 ease-in-out ${
                !showPrimary
                  ? "translate-y-0 opacity-100"
                  : "translate-y-full opacity-0"
              }`}
            >
              <span className="text-[#181d27] dark:text-zinc-200 text-md font-semibold">
                {formatCompactNumber(secondaryMetric.value)}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
