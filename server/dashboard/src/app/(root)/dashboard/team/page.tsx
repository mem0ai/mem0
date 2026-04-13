"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { api } from "@/utils/api";
import { TEAM_ENDPOINTS } from "@/utils/api-endpoints";
import { toast } from "@/components/ui/use-toast";
import { useAuth } from "@/hooks/use-auth";
import { UpgradeBanner } from "@/components/self-hosted/upgrade-banner";
import { Plus, Trash2 } from "lucide-react";

interface Member {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}

export default function TeamPage() {
  const { isAdmin } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");

  const fetchMembers = useCallback(async () => {
    try {
      const res = await api.get(TEAM_ENDPOINTS.BASE);
      setMembers(res.data || []);
    } catch {
      toast({ title: "Failed to load team members", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  const handleInvite = async () => {
    try {
      const res = await api.post(TEAM_ENDPOINTS.INVITE, { email: inviteEmail, role: inviteRole });
      toast({ title: "Invite sent", description: `Token: ${res.data.token}`, variant: "success" });
      setInviteOpen(false);
      setInviteEmail("");
      setInviteRole("member");
    } catch (error: any) {
      toast({ title: "Failed to send invite", description: typeof error === "string" ? error : error?.message, variant: "destructive" });
    }
  };

  const handleRemove = async (userId: string) => {
    if (!confirm("Remove this team member? Their API keys will be revoked.")) return;
    try {
      await api.delete(TEAM_ENDPOINTS.BY_ID(userId));
      toast({ title: "Member removed", variant: "success" });
      fetchMembers();
    } catch (error: any) {
      toast({ title: "Failed to remove member", description: typeof error === "string" ? error : error?.message, variant: "destructive" });
    }
  };

  const columns = [
    { key: "name" as keyof Member, label: "Name", width: 150 },
    { key: "email" as keyof Member, label: "Email", width: 200 },
    {
      key: "role" as keyof Member, label: "Role", width: 80,
      render: (value: string) => <Badge variant={value === "admin" ? "default" : "outline"} className="text-xs">{value}</Badge>,
    },
    {
      key: "created_at" as keyof Member, label: "Joined", width: 120,
      render: (value: string) => new Date(value).toLocaleDateString(),
    },
    ...(isAdmin ? [{
      key: "id" as keyof Member, label: "", width: 40,
      render: (_: string, row: Member) => (
        <Button variant="ghost" size="icon" onClick={() => handleRemove(row.id)} className="size-7">
          <Trash2 className="size-3.5 text-onSurface-danger-primary" />
        </Button>
      ),
    }] : []),
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold font-fustat">Team</h1>
        {isAdmin && (
          <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
            <DialogTrigger asChild><Button size="sm"><Plus className="size-4 mr-1" /> Invite</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Invite team member</DialogTitle>
                <DialogDescription>Send an invite link to a new team member.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 mt-2">
                <div className="space-y-2"><Label>Email</Label><Input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="member@company.com" /></div>
                <div className="space-y-2">
                  <Label>Role</Label>
                  <Select value={inviteRole} onValueChange={setInviteRole}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="member">Member</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={handleInvite} disabled={!inviteEmail} className="w-full">Send Invite</Button>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {members.length >= 3 && (
        <UpgradeBanner id="team-members-3" message="Growing team? Enterprise includes SSO, RBAC, and audit logs." ctaLabel="Talk to sales" ctaUrl="https://mem0.ai/enterprise" variant="enterprise" />
      )}

      {isLoading ? (
        <TableSkeleton rows={3} columns={4} />
      ) : (
        <DataTable data={members} columns={columns} getRowKey={(row) => row.id} />
      )}
    </div>
  );
}
