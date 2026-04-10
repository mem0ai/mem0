"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/utils/api";
import { MEMORY_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";
import { useAuth } from "@/hooks/use-auth";

export default function ConfigurationPage() {
  const { isAdmin } = useAuth();
  const [config, setConfig] = useState<Record<string, any>>({});
  const [isSaving, setIsSaving] = useState(false);

  // Flat fields for the form
  const [llmProvider, setLlmProvider] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [embedderProvider, setEmbedderProvider] = useState("");
  const [embedderModel, setEmbedderModel] = useState("");

  useEffect(() => {
    // Pre-fill would come from a GET /config endpoint.
    // For now, leave empty — fields show placeholder text.
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const newConfig: Record<string, any> = {
        version: "v1.1",
      };
      if (llmProvider) {
        newConfig.llm = {
          provider: llmProvider,
          config: {
            model: llmModel || undefined,
            api_key: llmApiKey || undefined,
          },
        };
      }
      if (embedderProvider) {
        newConfig.embedder = {
          provider: embedderProvider,
          config: { model: embedderModel || undefined },
        };
      }
      await api.post(MEMORY_ENDPOINTS.CONFIGURE, newConfig);
      toast({ title: "Configuration saved", variant: "success" });
    } catch (error: any) {
      toast({
        title: "Failed to save configuration",
        description: typeof error === "string" ? error : error?.message,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold font-fustat">Configuration</h1>

      <Card className="border-memBorder-primary">
        <CardHeader>
          <CardTitle className="text-sm">LLM Provider</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Provider</Label>
              <Input placeholder="openai" value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)} disabled={!isAdmin} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Model</Label>
              <Input placeholder="gpt-4.1-nano-2025-04-14" value={llmModel} onChange={(e) => setLlmModel(e.target.value)} disabled={!isAdmin} />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">API Key</Label>
            <Input type="password" placeholder="sk-..." value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} disabled={!isAdmin} />
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
              <Input placeholder="openai" value={embedderProvider} onChange={(e) => setEmbedderProvider(e.target.value)} disabled={!isAdmin} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Model</Label>
              <Input placeholder="text-embedding-3-small" value={embedderModel} onChange={(e) => setEmbedderModel(e.target.value)} disabled={!isAdmin} />
            </div>
          </div>
        </CardContent>
      </Card>

      {isAdmin && (
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Configuration"}
        </Button>
      )}

      <UpgradeBanner
        id="config-sso"
        message="Looking for SSO / SAML? Available in Enterprise."
        ctaLabel="Contact sales"
        ctaUrl="https://mem0.ai/enterprise"
        variant="enterprise"
        dismissible={false}
      />
    </div>
  );
}
