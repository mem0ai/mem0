"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy } from "lucide-react";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/error-message";
import { cn } from "@/lib/utils";
import { api } from "@/utils/api";
import { API_KEY_ENDPOINTS, MEMORY_ENDPOINTS } from "@/utils/api-endpoints";
import {
  buildProviderConfig,
  getEffectiveConfig,
} from "@/utils/self-hosted-config";

const STEPS = ["Admin Account", "Providers", "API Key", "Quick Test"];
const STEP_TITLES = [
  "Create your admin account",
  "Configure LLM provider",
  "Your API key",
  "Test your setup",
];

export default function SetupPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [step, setStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isPrefillingConfig, setIsPrefillingConfig] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [llmProvider, setLlmProvider] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");

  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [testSuccess, setTestSuccess] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    if (step !== 1) {
      setIsPrefillingConfig(false);
      return;
    }

    let active = true;
    setIsPrefillingConfig(true);

    const loadConfig = async () => {
      try {
        const res = await api.get(MEMORY_ENDPOINTS.CONFIGURE);
        const config = getEffectiveConfig(res.data);

        if (!active || !config?.llm) {
          return;
        }

        setLlmProvider((current) => current || config.llm?.provider || "");
        setLlmModel((current) => current || config.llm?.config?.model || "");
      } catch (err) {
        if (active) {
          setError(getErrorMessage(err, "Could not read server configuration"));
        }
      } finally {
        if (active) {
          setIsPrefillingConfig(false);
        }
      }
    };

    void loadConfig();

    return () => {
      active = false;
    };
  }, [step]);

  const handleStep1 = async () => {
    if (password !== confirmPassword) {
      setError("Passwords don't match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      await register(name, email, password);
      setStep(1);
    } catch (err) {
      setError(getErrorMessage(err, "Registration failed"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleStep2 = async () => {
    setError("");
    setIsLoading(true);

    try {
      const llm = buildProviderConfig({
        provider: llmProvider,
        model: llmModel,
        apiKey: llmApiKey,
      });

      if (llm) {
        await api.post(MEMORY_ENDPOINTS.CONFIGURE, {
          version: "v1.1",
          llm,
        });
      }

      setStep(2);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save provider configuration"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleStep3 = async () => {
    setError("");
    setIsLoading(true);

    try {
      const res = await api.post(API_KEY_ENDPOINTS.BASE, {
        label: "My First Key",
      });
      setApiKey(res.data.key);
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create API key"));
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

      if (!res.ok) {
        throw new Error("Test failed");
      }

      setTestSuccess(true);
    } catch (err) {
      setError(getErrorMessage(err, "Test failed"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-default-primary p-4">
      <div className="w-full max-w-[560px] space-y-6">
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className={cn(
                  "size-7 rounded-full flex items-center justify-center text-xs font-medium",
                  i <= step
                    ? "bg-memPurple-500 text-white"
                    : "bg-memNeutral-200 text-onSurface-default-tertiary",
                )}
              >
                {i < step ? <Check className="size-3.5" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    "w-8 h-[2px]",
                    i < step ? "bg-memPurple-500" : "bg-memNeutral-200",
                  )}
                />
              )}
            </div>
          ))}
        </div>
        <p className="text-center text-sm text-onSurface-default-tertiary">
          {STEPS[step]}
        </p>

        <Card className="border-memBorder-primary">
          <CardContent className="p-6 space-y-4">
            <div className="space-y-1">
              <h2 className="text-base font-semibold font-fustat">
                {STEP_TITLES[step]}
              </h2>
              {isPrefillingConfig && step === 1 && (
                <p className="text-xs text-onSurface-default-tertiary">
                  Checking server configuration...
                </p>
              )}
            </div>
            {error && (
              <p className="text-sm text-onSurface-danger-primary">{error}</p>
            )}

            {step === 0 && (
              <>
                <div className="space-y-1">
                  <Label htmlFor="setup-name">Name</Label>
                  <Input
                    id="setup-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="setup-email">Email</Label>
                  <Input
                    id="setup-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@company.com"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="setup-password">Password</Label>
                  <Input
                    id="setup-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 8 characters"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="setup-confirm-password">
                    Confirm Password
                  </Label>
                  <Input
                    id="setup-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>
                <Button
                  onClick={handleStep1}
                  disabled={isLoading || !name || !email || !password}
                  className="w-full"
                >
                  {isLoading ? "Creating..." : "Create Admin Account"}
                </Button>
              </>
            )}

            {step === 1 && (
              <>
                <div className="space-y-1">
                  <Label htmlFor="setup-llm-provider">LLM Provider</Label>
                  <Input
                    id="setup-llm-provider"
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value)}
                    placeholder="openai"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="setup-llm-model">Model</Label>
                  <Input
                    id="setup-llm-model"
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder="gpt-4.1-nano-2025-04-14"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="setup-llm-api-key">API Key</Label>
                  <Input
                    id="setup-llm-api-key"
                    type="password"
                    value={llmApiKey}
                    onChange={(e) => setLlmApiKey(e.target.value)}
                    placeholder="sk-..."
                  />
                </div>
                <p className="text-xs text-onSurface-default-tertiary">
                  Skip this step if the server is already configured.
                </p>
                <Button
                  onClick={handleStep2}
                  disabled={isLoading}
                  className="w-full"
                >
                  {isLoading ? "Saving..." : "Continue"}
                </Button>
              </>
            )}

            {step === 2 && !apiKey && (
              <Button
                onClick={handleStep3}
                disabled={isLoading}
                className="w-full"
              >
                {isLoading ? "Generating..." : "Generate API Key"}
              </Button>
            )}

            {step === 2 && apiKey && (
              <>
                <div className="space-y-1">
                  <Label htmlFor="setup-api-key">Your API Key</Label>
                  <div className="flex gap-2">
                    <Input
                      id="setup-api-key"
                      value={apiKey}
                      readOnly
                      className="font-mono text-sm"
                    />
                    <CopyToClipboard
                      text={apiKey}
                      onCopy={() => {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 2000);
                      }}
                    >
                      <Button variant="outline" size="icon">
                        {copied ? (
                          <Check className="size-4" />
                        ) : (
                          <Copy className="size-4" />
                        )}
                      </Button>
                    </CopyToClipboard>
                  </div>
                  <p className="text-xs text-onSurface-danger-primary">
                    Save this key. You will not see it again.
                  </p>
                </div>
                <Button onClick={() => setStep(3)} className="w-full">
                  Next
                </Button>
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
                  <Button
                    onClick={handleTest}
                    disabled={isLoading}
                    className="w-full"
                  >
                    {isLoading ? "Testing..." : "Run Test"}
                  </Button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-onSurface-positive-primary">
                      <Check className="size-4" /> Memory created successfully
                    </div>
                    <Button
                      onClick={() => router.push("/dashboard/")}
                      className="w-full"
                    >
                      Go to Dashboard
                    </Button>
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
