"use client";

import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";
import { useAuth } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/error-message";
import { api } from "@/utils/api";
import { AUTH_ENDPOINTS } from "@/utils/api-endpoints";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const { setTheme } = useTheme();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    if (user) {
      setName(user.name);
      setEmail(user.email);
    }
  }, [user]);

  const profileDirty =
    user !== null && (name !== user.name || email !== user.email);
  const profileValid = name.trim().length > 0 && email.trim().length > 0;

  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      await api.patch(AUTH_ENDPOINTS.ME, {
        name: name.trim(),
        email: email.trim(),
      });
      await refreshUser();
      toast({ title: "Profile updated", variant: "success" });
    } catch (error) {
      toast({
        title: "Failed to update profile",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast({
        title: "Passwords don't match",
        variant: "destructive",
      });
      return;
    }

    setSavingPassword(true);
    try {
      await api.post(AUTH_ENDPOINTS.CHANGE_PASSWORD, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast({ title: "Password updated", variant: "success" });
    } catch (error) {
      toast({
        title: "Failed to update password",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">Settings</h1>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="settings-name" className="text-xs">
                Name
              </Label>
              <Input
                id="settings-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="settings-email" className="text-xs">
                Email
              </Label>
              <Input
                id="settings-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>
          <Button
            onClick={handleSaveProfile}
            disabled={!profileDirty || !profileValid || savingProfile}
          >
            {savingProfile ? "Saving..." : "Save profile"}
          </Button>
        </CardContent>
      </Card>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Password</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="settings-current-password" className="text-xs">
              Current password
            </Label>
            <Input
              id="settings-current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="settings-new-password" className="text-xs">
                New password
              </Label>
              <Input
                id="settings-new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min 8 characters"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="settings-confirm-password" className="text-xs">
                Confirm new password
              </Label>
              <Input
                id="settings-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
          </div>
          <Button
            onClick={handleChangePassword}
            disabled={
              !currentPassword ||
              newPassword.length < 8 ||
              !confirmPassword ||
              savingPassword
            }
          >
            {savingPassword ? "Saving..." : "Update password"}
          </Button>
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
