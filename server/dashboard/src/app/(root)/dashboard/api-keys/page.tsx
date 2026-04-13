"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { api } from "@/utils/api";
import { API_KEY_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";
import { Plus, Copy, Check, Trash2 } from "lucide-react";
import { CopyToClipboard } from "react-copy-to-clipboard";

interface ApiKey {
  id: string;
  label: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await api.get(API_KEY_ENDPOINTS.BASE);
      setKeys(res.data || []);
    } catch {
      toast({ title: "Failed to load API keys", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const handleCreate = async () => {
    try {
      const res = await api.post(API_KEY_ENDPOINTS.BASE, { label: newLabel });
      setNewKey(res.data.key);
      fetchKeys();
    } catch (error: any) {
      toast({ title: "Failed to create key", description: typeof error === "string" ? error : error?.message, variant: "destructive" });
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    try {
      await api.delete(API_KEY_ENDPOINTS.BY_ID(keyId));
      toast({ title: "API key revoked", variant: "success" });
      fetchKeys();
    } catch (error: any) {
      toast({ title: "Failed to revoke key", description: typeof error === "string" ? error : error?.message, variant: "destructive" });
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (!open) { setNewKey(""); setNewLabel(""); setCopied(false); }
    setCreateOpen(open);
  };

  const columns = [
    { key: "label" as keyof ApiKey, label: "Label", width: 150 },
    { key: "key_prefix" as keyof ApiKey, label: "Key", width: 120, render: (value: string) => <code className="text-xs font-mono">{value}...</code> },
    { key: "created_at" as keyof ApiKey, label: "Created", width: 120, render: (value: string) => new Date(value).toLocaleDateString() },
    { key: "last_used_at" as keyof ApiKey, label: "Last Used", width: 120, render: (value: string | null) => value ? new Date(value).toLocaleDateString() : "Never" },
    { key: "id" as keyof ApiKey, label: "", width: 40, render: (_: string, row: ApiKey) => (
      <Button variant="ghost" size="icon" onClick={() => handleRevoke(row.id)} className="size-7"><Trash2 className="size-3.5 text-onSurface-danger-primary" /></Button>
    )},
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold font-fustat">API Keys</h1>
        <Dialog open={createOpen} onOpenChange={handleDialogClose}>
          <DialogTrigger asChild><Button size="sm"><Plus className="size-4 mr-1" /> Create Key</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Create API Key</DialogTitle></DialogHeader>
            {!newKey ? (
              <div className="space-y-4 mt-2">
                <div className="space-y-2"><Label>Label</Label><Input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="e.g. Production" /></div>
                <Button onClick={handleCreate} disabled={!newLabel} className="w-full">Create</Button>
              </div>
            ) : (
              <div className="space-y-4 mt-2">
                <div className="space-y-2">
                  <Label>Your API Key</Label>
                  <div className="flex gap-2">
                    <Input value={newKey} readOnly className="font-mono text-sm" />
                    <CopyToClipboard text={newKey} onCopy={() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }}>
                      <Button variant="outline" size="icon">{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</Button>
                    </CopyToClipboard>
                  </div>
                  <p className="text-xs text-onSurface-danger-primary">Save this key -- you won't see it again.</p>
                </div>
                <Button onClick={() => handleDialogClose(false)} className="w-full">Done</Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {keys.length >= 3 && (
        <UpgradeBanner id="api-keys-3" message="Managing multiple apps? Cloud offers project-based isolation." ctaLabel="Explore Cloud" ctaUrl="https://app.mem0.ai" variant="cloud" />
      )}

      {isLoading ? (
        <TableSkeleton rows={3} columns={4} />
      ) : keys.length === 0 ? (
        <EmptyState title="No API keys yet" description="Create your first API key to start using the Mem0 API." />
      ) : (
        <DataTable data={keys} columns={columns} getRowKey={(row) => row.id} />
      )}
    </div>
  );
}
