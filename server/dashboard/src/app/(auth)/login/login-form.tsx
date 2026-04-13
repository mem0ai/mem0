"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { AUTH_ENDPOINTS } from "@/utils/api-endpoints";
import ThemeAwareLogo from "@/components/misc/theme-aware-logo";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isLoading && user) {
      router.push(searchParams.get("next") || "/dashboard/");
    }
  }, [user, isLoading, router, searchParams]);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}${AUTH_ENDPOINTS.SETUP_STATUS}`)
      .then((res) => res.ok && res.json())
      .then((data) => data?.needsSetup && router.push("/setup"))
      .catch(() => {});
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      router.push(searchParams.get("next") || "/dashboard/");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-default-primary p-4">
      <div className="w-full max-w-[400px] space-y-8">
        <div className="flex justify-center">
          <ThemeAwareLogo width={100} height={32} />
        </div>
        <Card className="border-memBorder-primary">
          <CardContent className="p-6">
            <h1 className="text-lg font-semibold font-fustat text-center mb-6">Sign in to your account</h1>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <p className="text-sm text-onSurface-danger-primary bg-surface-danger-primary px-3 py-2 rounded">{error}</p>
              )}
              <div className="space-y-1">
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@company.com" required autoFocus />
              </div>
              <div className="space-y-1">
                <Label>Password</Label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
