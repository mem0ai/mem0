"use client";

import { LockedPage } from "@/components/self-hosted/locked-page";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

function WebhooksMockup() {
  return (
    <Card className="border-memBorder-primary">
      <CardContent className="p-6 space-y-4">
        <div className="space-y-2">
          <Label>Endpoint URL</Label>
          <Input placeholder="https://your-app.com/webhooks/mem0" disabled />
        </div>
        <div className="space-y-2">
          <Label>Events</Label>
          <div className="flex flex-col gap-2">
            {[
              "memory.created",
              "memory.updated",
              "memory.deleted",
              "search.performed",
            ].map((event) => (
              <div key={event} className="flex items-center gap-2">
                <Checkbox disabled checked={event === "memory.created"} />
                <Label className="text-sm font-normal">{event}</Label>
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <Label>Signing Secret</Label>
          <Input placeholder="whsec_..." disabled type="password" />
        </div>
        <Button disabled>Create Webhook</Button>
      </CardContent>
    </Card>
  );
}

export default function WebhooksPage() {
  return (
    <LockedPage
      title="Webhooks"
      description="Get notified when memories are created, updated, or deleted."
      previewContent={<WebhooksMockup />}
      utmMedium="dashboard-locked-webhooks"
    />
  );
}
