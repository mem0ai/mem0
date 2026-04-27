"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";
import { getErrorMessage } from "@/lib/error-message";
import { api } from "@/utils/api";
import { MEMORY_ENDPOINTS } from "@/utils/api-endpoints";
import {
  buildProviderConfig,
  getEffectiveConfig,
} from "@/utils/self-hosted-config";
import { useAuth } from "@/hooks/use-auth";
import { useApiQuery } from "@/hooks/use-api-query";

type BundledProviders = {
  llm: string[];
  embedder: string[];
};

export default function ConfigurationPage() {
  const { isAdmin } = useAuth();
  const [isSaving, setIsSaving] = useState(false);
  const [llmProvider, setLlmProvider] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [embedderProvider, setEmbedderProvider] = useState("");
  const [embedderModel, setEmbedderModel] = useState("");

  const { data: config, isLoading: isPrefilling } = useApiQuery(
    async () => {
      const res = await api.get(MEMORY_ENDPOINTS.CONFIGURE);
      return getEffectiveConfig(res.data);
    },
    { errorToast: "Failed to load server configuration" },
  );

  const { data: providers } = useApiQuery<BundledProviders>(
    async () => {
      const res = await api.get<BundledProviders>(
        MEMORY_ENDPOINTS.CONFIGURE_PROVIDERS,
      );
      return res.data;
    },
    { errorToast: "Failed to load bundled providers" },
  );

  useEffect(() => {
    if (!config) return;
    setLlmProvider((current) => current || config.llm?.provider || "");
    setLlmModel((current) => current || config.llm?.config?.model || "");
    setEmbedderProvider(
      (current) => current || config.embedder?.provider || "",
    );
    setEmbedderModel(
      (current) => current || config.embedder?.config?.model || "",
    );
  }, [config]);

  const handleSave = async () => {
    setIsSaving(true);

    try {
      const llm = buildProviderConfig({
        provider: llmProvider,
        model: llmModel,
        apiKey: llmApiKey,
      });
      const embedder = buildProviderConfig({
        provider: embedderProvider,
        model: embedderModel,
      });

      const newConfig: Record<string, unknown> = {
        version: "v1.1",
      };

      if (llm) {
        newConfig.llm = llm;
      }

      if (embedder) {
        newConfig.embedder = embedder;
      }

      await api.post(MEMORY_ENDPOINTS.CONFIGURE, newConfig);
      toast({ title: "Configuration saved", variant: "success" });
    } catch (error) {
      toast({
        title: "Failed to save configuration",
        description: getErrorMessage(error),
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold font-fustat">Configuration</h1>
        {isPrefilling && (
          <p className="text-sm text-onSurface-default-tertiary">
            Loading effective server configuration...
          </p>
        )}
      </div>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">LLM Provider</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Provider</Label>
              <Select
                value={llmProvider}
                onValueChange={setLlmProvider}
                disabled={!isAdmin || !providers}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers?.llm.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Model</Label>
              <Input
                placeholder="gpt-4.1-nano-2025-04-14"
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                disabled={!isAdmin}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">API Key</Label>
            <Input
              type="password"
              placeholder="sk-..."
              value={llmApiKey}
              onChange={(e) => setLlmApiKey(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">Embedding Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Provider</Label>
              <Select
                value={embedderProvider}
                onValueChange={setEmbedderProvider}
                disabled={!isAdmin || !providers}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers?.embedder.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Model</Label>
              <Input
                placeholder="text-embedding-3-small"
                value={embedderModel}
                onChange={(e) => setEmbedderModel(e.target.value)}
                disabled={!isAdmin}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <p className="text-xs text-onSurface-default-tertiary">
        Need another provider? Install its Python package, rebuild the image,
        and extend the bundled list. See the{" "}
        <a
          href="https://docs.mem0.ai/open-source/setup#supported-providers"
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-4 hover:text-onSurface-default-primary"
        >
          setup guide
        </a>
        .
      </p>

      {isAdmin && (
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Configuration"}
        </Button>
      )}

      <UpgradeBanner
        id="config-sso"
        message="Looking for SSO / SAML? Available in Enterprise."
        ctaLabel="Contact sales"
        ctaUrl="https://app.mem0.ai/enterprise?utm_source=oss&utm_medium=dashboard-configuration-sso"
        variant="enterprise"
      />
    </div>
  );
}
