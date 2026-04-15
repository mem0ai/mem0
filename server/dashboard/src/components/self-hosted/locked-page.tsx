"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Lock } from "lucide-react";

interface LockedPageProps {
  title: string;
  description: string;
  previewContent: React.ReactNode;
  cloudUrl?: string;
  salesUrl?: string;
}

export function LockedPage({
  title,
  description,
  previewContent,
  cloudUrl = "https://app.mem0.ai?utm_source=oss&utm_medium=dashboard-locked-page",
  salesUrl = "https://app.mem0.ai/enterprise?utm_source=oss&utm_medium=dashboard-locked-page",
}: LockedPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold font-fustat flex items-center gap-2">
          {title}
          <Lock className="size-4 text-onSurface-default-tertiary" />
        </h1>
        <p className="text-sm text-onSurface-default-secondary mt-1">
          {description}
        </p>
      </div>

      <div className="opacity-60 pointer-events-none select-none">
        {previewContent}
      </div>

      <Card className="border-memBorder-primary">
        <CardContent className="flex flex-col sm:flex-row items-center gap-4 py-6">
          <div className="flex-1">
            <p className="text-sm font-medium">
              This feature is available in Mem0 Cloud and Enterprise.
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="default" asChild>
              <a href={cloudUrl} target="_blank" rel="noopener noreferrer">
                Start free on Cloud
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a href={salesUrl} target="_blank" rel="noopener noreferrer">
                Talk to sales
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
