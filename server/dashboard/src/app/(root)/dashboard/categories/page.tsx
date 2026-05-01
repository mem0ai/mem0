"use client";

import { LockedPage } from "@/components/self-hosted/locked-page";
import { Card, CardContent } from "@/components/ui/card";

function CategoriesMockup() {
  const categories = ["Health", "Preferences", "Work"];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {categories.map((cat) => (
        <Card key={cat} className="border-memBorder-primary">
          <CardContent className="p-4">
            <p className="text-sm font-medium mb-3">{cat}</p>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-8 bg-surface-default-secondary rounded mb-2"
              />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function CategoriesPage() {
  return (
    <LockedPage
      title="Custom Categories"
      description="Organize memories by domain -- health, preferences, work, and more."
      previewContent={<CategoriesMockup />}
      utmMedium="dashboard-locked-categories"
    />
  );
}
