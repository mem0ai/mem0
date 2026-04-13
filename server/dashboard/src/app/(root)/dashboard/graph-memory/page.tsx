"use client";

import { LockedPage } from "@/components/self-hosted/locked-page";
import { Card, CardContent } from "@/components/ui/card";

function GraphMemoryMockup() {
  const nodes = [
    { label: "User", x: "50%", y: "18%" },
    { label: "Preference", x: "18%", y: "50%" },
    { label: "Project", x: "50%", y: "50%" },
    { label: "Device", x: "82%", y: "50%" },
    { label: "Memory", x: "50%", y: "82%" },
  ];

  return (
    <Card className="border-memBorder-primary">
      <CardContent className="p-6">
        <div className="relative h-[280px] overflow-hidden rounded-2xl border border-memBorder-primary bg-surface-default-secondary">
          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <path
              d="M50 18 L50 50"
              stroke="currentColor"
              className="text-memBorder-primary"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
            <path
              d="M50 50 L18 50"
              stroke="currentColor"
              className="text-memBorder-primary"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
            <path
              d="M50 50 L82 50"
              stroke="currentColor"
              className="text-memBorder-primary"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
            <path
              d="M50 50 L50 82"
              stroke="currentColor"
              className="text-memBorder-primary"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
          </svg>
          {nodes.map((node) => (
            <div
              key={node.label}
              className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full border border-memBorder-primary bg-surface-default-primary px-3 py-2 text-xs font-medium shadow-sm"
              style={{ left: node.x, top: node.y }}
            >
              {node.label}
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {[
            { label: "Relationships", value: "128" },
            { label: "Inference paths", value: "36" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-memBorder-primary bg-surface-default-secondary p-3"
            >
              <p className="text-xs text-onSurface-default-tertiary">
                {item.label}
              </p>
              <p className="mt-1 text-lg font-semibold">{item.value}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function GraphMemoryPage() {
  return (
    <LockedPage
      title="Graph Memory"
      description="Model memory as a connected graph of entities, preferences, and relationships."
      previewContent={<GraphMemoryMockup />}
    />
  );
}
