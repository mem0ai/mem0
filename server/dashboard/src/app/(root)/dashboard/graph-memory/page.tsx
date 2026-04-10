"use client";

import { LockedPage } from "@/components/self-hosted/locked-page";
import { Card, CardContent } from "@/components/ui/card";

function GraphMockup() {
  return (
    <Card className="border-memBorder-primary">
      <CardContent className="p-8 flex items-center justify-center min-h-[300px]">
        <svg viewBox="0 0 400 250" className="w-full max-w-md text-onSurface-default-tertiary">
          {/* Nodes */}
          <circle cx="200" cy="50" r="20" fill="currentColor" opacity="0.2" stroke="currentColor" strokeWidth="1" />
          <circle cx="100" cy="150" r="16" fill="currentColor" opacity="0.15" stroke="currentColor" strokeWidth="1" />
          <circle cx="300" cy="150" r="16" fill="currentColor" opacity="0.15" stroke="currentColor" strokeWidth="1" />
          <circle cx="150" cy="220" r="14" fill="currentColor" opacity="0.1" stroke="currentColor" strokeWidth="1" />
          <circle cx="250" cy="220" r="14" fill="currentColor" opacity="0.1" stroke="currentColor" strokeWidth="1" />
          {/* Edges */}
          <line x1="200" y1="70" x2="100" y2="134" stroke="currentColor" opacity="0.3" strokeWidth="1" />
          <line x1="200" y1="70" x2="300" y2="134" stroke="currentColor" opacity="0.3" strokeWidth="1" />
          <line x1="100" y1="166" x2="150" y2="206" stroke="currentColor" opacity="0.3" strokeWidth="1" />
          <line x1="300" y1="166" x2="250" y2="206" stroke="currentColor" opacity="0.3" strokeWidth="1" />
          <line x1="150" y1="220" x2="250" y2="220" stroke="currentColor" opacity="0.2" strokeWidth="1" strokeDasharray="4" />
          {/* Labels */}
          <text x="200" y="54" textAnchor="middle" fontSize="10" fill="currentColor" opacity="0.5">User</text>
          <text x="100" y="154" textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.5">likes</text>
          <text x="300" y="154" textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.5">works at</text>
        </svg>
      </CardContent>
    </Card>
  );
}

export default function GraphMemoryPage() {
  return (
    <LockedPage
      title="Graph Memory"
      description="Visualize relationships between entities, users, and memories."
      previewContent={<GraphMockup />}
    />
  );
}
