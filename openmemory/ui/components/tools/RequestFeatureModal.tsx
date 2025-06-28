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
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Send, Lightbulb } from 'lucide-react';
import apiClient from '@/lib/apiClient';

interface RequestFeatureModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RequestFeatureModal({ open, onOpenChange }: RequestFeatureModalProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    featureIdea: '',
    useCase: '',
    additionalInfo: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.featureIdea || !formData.useCase) {
      toast({
        variant: "destructive",
        title: "Missing Information",
        description: "Please describe your idea and use case.",
      });
      return;
    }

    setIsLoading(true);

    try {
      // Ensure user data is available
      if (!user?.email || !user?.id) {
        toast({
          variant: "destructive",
          title: "Authentication Error",
          description: "User authentication data is missing. Please try refreshing the page.",
        });
        setIsLoading(false);
        return;
      }

      const requestPayload = {
        appName: `Feature: ${formData.featureIdea}`,
        useCase: formData.useCase,
        priority: "low",
        additionalInfo: formData.additionalInfo || "",
        userEmail: user.email,
        userId: user.id
      };

      // Debug logging
      console.log("Feature request payload:", requestPayload);
      console.log("User data:", { email: user.email, id: user.id });

      await apiClient.post('/api/v1/integrations/request', requestPayload);

      toast({
        title: "Thank You!",
        description: "Your feature request has been submitted. We appreciate your feedback!",
      });

      setFormData({
        featureIdea: '',
        useCase: '',
        additionalInfo: ''
      });
      onOpenChange(false);

    } catch (error: any) {
      console.error("Feature request error:", error);
      console.error("Error response:", error.response?.data);
      
      toast({
        variant: "destructive",
        title: "Submission Failed",
        description: error.response?.data?.detail || "Failed to submit your request. Please try again.",
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
        className="sm:max-w-lg bg-card border-border text-foreground shadow-lg"
        onOpenChange={onOpenChange}
      >
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-14 h-14 rounded-lg bg-secondary flex items-center justify-center mb-4">
            <Lightbulb className="w-8 h-8 text-primary" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            Share Your Idea
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            We're a small team and love hearing from our users. What should we build next to make your memory even more powerful?
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="featureIdea">Tool or Feature Idea *</Label>
            <Input
              id="featureIdea"
              placeholder="e.g., Automatic meeting summaries, AI-powered goal tracking..."
              value={formData.featureIdea}
              onChange={(e) => handleInputChange('featureIdea', e.target.value)}
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="useCase">How would this help you? *</Label>
            <Textarea
              id="useCase"
              placeholder="What problem would this solve? How would you use it in your daily workflow?"
              value={formData.useCase}
              onChange={(e) => handleInputChange('useCase', e.target.value)}
              className="min-h-[100px]"
              disabled={isLoading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="additionalInfo">Additional Details (Optional)</Label>
            <Textarea
              id="additionalInfo"
              placeholder="Any other details, examples, or links to share?"
              value={formData.additionalInfo}
              onChange={(e) => handleInputChange('additionalInfo', e.target.value)}
              className="min-h-[60px]"
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
                  Submit Idea
                </>
              )}
            </Button>
          </div>
        </form>
      </MobileOptimizedDialogContent>
    </MobileOptimizedDialog>
  );
} 