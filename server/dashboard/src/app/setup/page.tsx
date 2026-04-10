"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, Copy } from "lucide-react";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

const STEPS = ["Admin Account", "Providers", "API Key", "Quick Test"];

export default function SetupPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [step, setStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 1: Admin
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Step 2: Providers
  const [llmProvider, setLlmProvider] = useState("openai");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");

  // Step 3: API Key
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);

  // Step 4: Test
  const [testSuccess, setTestSuccess] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  const handleStep1 = async () => {
    if (password !== confirmPassword) { setError("Passwords don't match"); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    setError("");
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Registration failed");
      }
      await login(email, password);
      setStep(1);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStep2 = async () => {
    setError("");
    setIsLoading(true);
    try {
      if (llmApiKey) {
        await fetch(`${apiUrl}/configure`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version: "v1.1",
            llm: { provider: llmProvider, config: { model: llmModel || undefined, api_key: llmApiKey } },
          }),
        });
      }
      setStep(2);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStep3 = async () => {
    setError("");
    setIsLoading(true);
    try {
      const { getAccessToken } = await import("@/utils/api");
      const token = getAccessToken();
      const res = await fetch(`${apiUrl}/api-keys/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ label: "My First Key" }),
      });
      if (!res.ok) throw new Error("Failed to create API key");
      const data = await res.json();
      setApiKey(data.key);
      setStep(3);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleTest = async () => {
    setError("");
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/memories`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify({
          messages: [{ role: "user", content: "I like to hike on weekends." }],
          user_id: "setup-test",
        }),
      });
      if (!res.ok) throw new Error("Test failed");
      setTestSuccess(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-default-primary p-4">
      <div className="w-full max-w-[560px] space-y-6">
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div className={cn(
                "size-7 rounded-full flex items-center justify-center text-xs font-medium",
                i < step ? "bg-memPurple-500 text-white" :
                i === step ? "bg-memPurple-500 text-white" :
                "bg-memNeutral-200 text-onSurface-default-tertiary"
              )}>
                {i < step ? <Check className="size-3.5" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn("w-8 h-[2px]", i < step ? "bg-memPurple-500" : "bg-memNeutral-200")} />
              )}
            </div>
          ))}
        </div>
        <p className="text-center text-sm text-onSurface-default-tertiary">{STEPS[step]}</p>

        <Card className="border-memBorder-primary">
          <CardContent className="p-6 space-y-4">
            {error && <p className="text-sm text-onSurface-danger-primary">{error}</p>}

            {step === 0 && (
              <>
                <div className="space-y-1"><Label>Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" /></div>
                <div className="space-y-1"><Label>Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@company.com" /></div>
                <div className="space-y-1"><Label>Password</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 8 characters" /></div>
                <div className="space-y-1"><Label>Confirm Password</Label><Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} /></div>
                <Button onClick={handleStep1} disabled={isLoading || !name || !email || !password} className="w-full">{isLoading ? "Creating..." : "Create Admin Account"}</Button>
              </>
            )}

            {step === 1 && (
              <>
                <div className="space-y-1"><Label>LLM Provider</Label><Input value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} /></div>
                <div className="space-y-1"><Label>Model</Label><Input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} placeholder="gpt-4.1-nano-2025-04-14" /></div>
                <div className="space-y-1"><Label>API Key</Label><Input type="password" value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} placeholder="sk-..." /></div>
                <p className="text-xs text-onSurface-default-tertiary">Skip if already configured via .env</p>
                <Button onClick={handleStep2} disabled={isLoading} className="w-full">{isLoading ? "Saving..." : "Next"}</Button>
              </>
            )}

            {step === 2 && !apiKey && (
              <Button onClick={handleStep3} disabled={isLoading} className="w-full">{isLoading ? "Generating..." : "Generate API Key"}</Button>
            )}

            {step === 2 && apiKey && (
              <>
                <div className="space-y-1">
                  <Label>Your API Key</Label>
                  <div className="flex gap-2">
                    <Input value={apiKey} readOnly className="font-mono text-sm" />
                    <CopyToClipboard text={apiKey} onCopy={() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }}>
                      <Button variant="outline" size="icon">{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</Button>
                    </CopyToClipboard>
                  </div>
                  <p className="text-xs text-onSurface-danger-primary">Save this key -- you won't see it again.</p>
                </div>
                <Button onClick={() => setStep(3)} className="w-full">Next</Button>
              </>
            )}

            {step === 3 && (
              <>
                <div className="space-y-1">
                  <Label>Test your setup</Label>
                  <pre className="text-xs bg-surface-default-secondary p-3 rounded font-mono overflow-x-auto">{`curl -X POST ${apiUrl}/memories \\
  -H "X-API-Key: ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user", "content": "I like hiking"}], "user_id": "test"}'`}</pre>
                </div>
                {!testSuccess ? (
                  <Button onClick={handleTest} disabled={isLoading} className="w-full">{isLoading ? "Testing..." : "Run Test"}</Button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-onSurface-positive-primary">
                      <Check className="size-4" /> Memory created successfully
                    </div>
                    <Button onClick={() => router.push("/dashboard/")} className="w-full">Go to Dashboard</Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
