"use client";

import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { 
  MobileOptimizedDialog, 
  MobileOptimizedDialogContent, 
  MobileOptimizedDialogHeader, 
  MobileOptimizedDialogTitle, 
  MobileOptimizedDialogDescription 
} from '@/components/ui/mobile-optimized-dialog';
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
    <MobileOptimizedDialog open={open} onOpenChange={onOpenChange}>
      <MobileOptimizedDialogContent 
        className="sm:max-w-md bg-card border-border text-foreground shadow-2xl"
        onOpenChange={onOpenChange}
      >
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-secondary border border-border flex items-center justify-center mb-4">
            <Plus className="w-8 h-8 text-muted-foreground" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            Request New Integration
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            Tell us which app you'd like to connect to Jean Memory
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="appName" className="text-sm font-medium">
              App/Service Name *
            </Label>
            <Input
              id="appName"
              placeholder="e.g., Slack, Discord, Notion..."
              value={formData.appName}
              onChange={(e) => handleInputChange('appName', e.target.value)}
              className="bg-background border-border"
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="useCase" className="text-sm font-medium">
              How would you use this integration? *
            </Label>
            <Textarea
              id="useCase"
              placeholder="Describe your specific use case and how this integration would help you..."
              value={formData.useCase}
              onChange={(e) => handleInputChange('useCase', e.target.value)}
              className="bg-background border-border min-h-[80px]"
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="priority" className="text-sm font-medium">
              Priority Level *
            </Label>
            <Select value={formData.priority} onValueChange={(value) => handleInputChange('priority', value)} disabled={isLoading}>
              <SelectTrigger className="bg-background border-border">
                <SelectValue placeholder="Select priority level" />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                <SelectItem value="high" className="hover:bg-accent">High - I need this urgently</SelectItem>
                <SelectItem value="medium" className="hover:bg-accent">Medium - Would be very helpful</SelectItem>
                <SelectItem value="low" className="hover:bg-accent">Low - Nice to have</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="additionalInfo" className="text-sm font-medium">
              Additional Information
            </Label>
            <Textarea
              id="additionalInfo"
              placeholder="Any additional details, links, or requirements..."
              value={formData.additionalInfo}
              onChange={(e) => handleInputChange('additionalInfo', e.target.value)}
              className="bg-background border-border min-h-[60px]"
              disabled={isLoading}
            />
          </div>

          <div className="flex gap-3 pt-4 max-sm:flex-col max-sm:space-y-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="flex-1"
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1"
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
      </MobileOptimizedDialogContent>
    </MobileOptimizedDialog>
  );
} 