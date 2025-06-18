"use client";

import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Send, Plus } from 'lucide-react';
import apiClient from '@/lib/apiClient';

interface RequestIntegrationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RequestIntegrationModal({ open, onOpenChange }: RequestIntegrationModalProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    appName: '',
    useCase: '',
    priority: '',
    additionalInfo: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.appName || !formData.useCase || !formData.priority) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please fill in all required fields.",
      });
      return;
    }

    setIsLoading(true);

    try {
      await apiClient.post('/api/v1/integrations/request', {
        appName: formData.appName,
        useCase: formData.useCase,
        priority: formData.priority,
        additionalInfo: formData.additionalInfo,
        userEmail: user?.email,
        userId: user?.id
      });

      toast({
        title: "Request Submitted!",
        description: "Your integration request has been sent. We'll get back to you soon!",
      });

      // Reset form and close modal
      setFormData({
        appName: '',
        useCase: '',
        priority: '',
        additionalInfo: ''
      });
      onOpenChange(false);

    } catch (error: any) {
      toast({
        variant: "destructive",
        title: "Submission Failed",
        description: error.response?.data?.detail || "Failed to submit request. Please try again.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800 text-white shadow-2xl shadow-zinc-500/10">
        <DialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center mb-4">
            <Plus className="w-8 h-8 text-zinc-300" />
          </div>
          <DialogTitle className="text-2xl font-bold">
            Request New Integration
          </DialogTitle>
          <DialogDescription className="text-zinc-400 pt-1">
            Tell us which app you'd like to connect to Jean Memory
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 px-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="appName" className="text-sm font-medium text-zinc-300">
              App/Service Name *
            </Label>
            <Input
              id="appName"
              placeholder="e.g., Slack, Discord, Notion..."
              value={formData.appName}
              onChange={(e) => handleInputChange('appName', e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-500"
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="useCase" className="text-sm font-medium text-zinc-300">
              How would you use this integration? *
            </Label>
            <Textarea
              id="useCase"
              placeholder="Describe your specific use case and how this integration would help you..."
              value={formData.useCase}
              onChange={(e) => handleInputChange('useCase', e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 min-h-[80px]"
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="priority" className="text-sm font-medium text-zinc-300">
              Priority Level *
            </Label>
            <Select value={formData.priority} onValueChange={(value) => handleInputChange('priority', value)} disabled={isLoading}>
              <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                <SelectValue placeholder="Select priority level" />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-700">
                <SelectItem value="high" className="text-zinc-100 hover:bg-zinc-800">High - I need this urgently</SelectItem>
                <SelectItem value="medium" className="text-zinc-100 hover:bg-zinc-800">Medium - Would be very helpful</SelectItem>
                <SelectItem value="low" className="text-zinc-100 hover:bg-zinc-800">Low - Nice to have</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="additionalInfo" className="text-sm font-medium text-zinc-300">
              Additional Information
            </Label>
            <Textarea
              id="additionalInfo"
              placeholder="Any additional details, links, or requirements..."
              value={formData.additionalInfo}
              onChange={(e) => handleInputChange('additionalInfo', e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 min-h-[60px]"
              disabled={isLoading}
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="flex-1 border border-zinc-700 hover:bg-zinc-800"
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1 bg-white hover:bg-zinc-200 text-black"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Submit Request
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
} 