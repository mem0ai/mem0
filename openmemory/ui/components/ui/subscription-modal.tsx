"use client"

import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check, Key, Shield } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface SubscriptionError {
  error: string;
  title: string;
  message: string;
  description: string;
  benefits: string[];
  action: {
    text: string;
    url: string;
  };
  current_tier?: string;
  current_status?: string;
}

interface SubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  error: SubscriptionError | null;
}

export function SubscriptionModal({ isOpen, onClose, error }: SubscriptionModalProps) {
  const router = useRouter();
  
  if (!error) return null;

  const handleUpgrade = () => {
    if (error.action.url.startsWith('mailto:')) {
      window.location.href = error.action.url;
    } else {
      router.push(error.action.url);
    }
    onClose();
  };

  const isEnterprise = error.error === 'enterprise_required';
  const isInactive = error.current_status && error.current_status !== 'active';

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="text-center space-y-4">
          <div className="mx-auto w-12 h-12 bg-muted rounded-lg flex items-center justify-center">
            {isEnterprise ? (
              <Shield className="w-6 h-6 text-muted-foreground" />
            ) : (
              <Key className="w-6 h-6 text-muted-foreground" />
            )}
          </div>
          <DialogTitle className="text-xl font-semibold">
            {isEnterprise ? 'Enterprise Required' : 'Pro Features'}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4">
          {/* Current Status */}
          {error.current_tier && (
            <div className="text-center">
              <Badge variant="secondary" className="text-xs">
                Current: {error.current_tier.charAt(0).toUpperCase() + error.current_tier.slice(1).toLowerCase()}
                {isInactive && ` (${error.current_status})`}
              </Badge>
            </div>
          )}

          {/* Message */}
          <div className="text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              {error.message}
            </p>
          </div>

          {/* Benefits */}
          <div className="bg-muted/50 rounded-lg p-4 space-y-3">
            <h4 className="font-medium text-sm">
              {isEnterprise ? 'Enterprise includes:' : 'Pro includes:'}
            </h4>
            <div className="space-y-2">
              {error.benefits.map((benefit, index) => (
                <div key={index} className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                  <span className="text-sm text-muted-foreground">{benefit}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Pricing for Pro */}
          {!isEnterprise && (
            <div className="text-center py-3 bg-card border rounded-lg">
              <div className="text-lg font-semibold">$19/month</div>
              <div className="text-xs text-muted-foreground">Cancel anytime</div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Not now
            </Button>
            <Button onClick={handleUpgrade} className="flex-1">
              {isEnterprise ? 'Contact Sales' : 'Upgrade to Pro'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
} 