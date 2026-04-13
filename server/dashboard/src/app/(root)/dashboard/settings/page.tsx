"use client";

import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "next-themes";

export default function SettingsPage() {
  const { user } = useAuth();
  const { setTheme } = useTheme();

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">Settings</h1>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Name</Label>
              <Input value={user?.name || ""} disabled />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Email</Label>
              <Input value={user?.email || ""} disabled />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Appearance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <span className="text-sm text-onSurface-default-secondary">
              Theme
            </span>
            <button
              onClick={() => setTheme("light")}
              className="p-2 rounded hover:bg-surface-default-secondary-hover"
            >
              <Sun className="size-4" />
            </button>
            <button
              onClick={() => setTheme("dark")}
              className="p-2 rounded hover:bg-surface-default-secondary-hover"
            >
              <Moon className="size-4" />
            </button>
            <button
              onClick={() => setTheme("system")}
              className="p-2 rounded hover:bg-surface-default-secondary-hover"
            >
              <Monitor className="size-4" />
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
