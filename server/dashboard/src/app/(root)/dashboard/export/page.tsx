"use client";

import { LockedPage } from "@/components/self-hosted/locked-page";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

function ExportMockup() {
  return (
    <div className="space-y-4">
      <Card className="border-memBorder-primary">
        <CardContent className="p-6 space-y-4">
          <div className="space-y-2">
            <Label>Format</Label>
            <div className="flex gap-2">
              {["JSON", "CSV", "Pydantic Schema"].map((fmt) => (
                <Button
                  key={fmt}
                  variant="outline"
                  size="sm"
                  disabled
                  className={fmt === "JSON" ? "border-memPurple-300" : ""}
                >
                  {fmt}
                </Button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <Label>Sample output</Label>
            <Card className="border-memBorder-primary bg-surface-default-secondary">
              <CardContent className="p-3">
                <pre className="text-xs text-onSurface-default-secondary font-mono whitespace-pre-wrap">
                  {`{
  "memories": [
    {
      "id": "mem_abc123",
      "content": "User prefers dark mode",
      "user_id": "user_1",
      "created_at": "2026-04-10T12:00:00Z"
    }
  ],
  "total": 1247
}`}
                </pre>
              </CardContent>
            </Card>
          </div>
          <Button disabled>Export Memories</Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ExportPage() {
  return (
    <LockedPage
      title="Export"
      description="Export your memories in JSON, CSV, or Pydantic schema format."
      previewContent={<ExportMockup />}
      utmMedium="dashboard-locked-export"
    />
  );
}
