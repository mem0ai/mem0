"use client";

import { useState } from 'react';
import {
  MobileOptimizedDialog,
  MobileOptimizedDialogContent,
  MobileOptimizedDialogHeader,
  MobileOptimizedDialogTitle,
  MobileOptimizedDialogDescription,
} from '@/components/ui/mobile-optimized-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, MessageSquare, Shield, Smartphone, CheckCircle } from 'lucide-react';
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/lib/apiClient';

interface SmsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ModalStep = 'phone' | 'verification' | 'success' | 'error';

interface ModalState {
  step: ModalStep;
  phoneNumber: string;
  verificationCode: string;
  loading: boolean;
  error: string | null;
  expiresInMinutes: number;
}

export function SmsModal({ open, onOpenChange }: SmsModalProps) {
  const { user } = useAuth();
  const { toast } = useToast();
  
  const [state, setState] = useState<ModalState>({
    step: 'phone',
    phoneNumber: '',
    verificationCode: '',
    loading: false,
    error: null,
    expiresInMinutes: 10
  });

  const resetModal = () => {
    setState({
      step: 'phone',
      phoneNumber: '',
      verificationCode: '',
      loading: false,
      error: null,
      expiresInMinutes: 10
    });
  };

  const handleClose = () => {
    onOpenChange(false);
    setTimeout(resetModal, 300); // Reset after animation
  };



  const handlePhoneSubmit = async () => {
    if (!state.phoneNumber.trim()) {
      setState(prev => ({ ...prev, error: 'Please enter a phone number' }));
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await apiClient.post('/api/v1/profile/phone/add', {
        phone_number: state.phoneNumber
      });

      setState(prev => ({
        ...prev,
        loading: false,
        step: 'verification',
        expiresInMinutes: response.data.expires_in_minutes || 10
      }));

      toast({
        title: "Verification code sent",
        description: `Check your phone for a 6-digit code from Jean Memory`,
      });

    } catch (error: any) {
      let errorMessage = "Failed to send verification code";
      
      if (error.response?.status === 402) {
        errorMessage = "This feature requires a Pro subscription. Upgrade to continue.";
      } else if (error.response?.status === 409) {
        errorMessage = "This phone number is already registered to another account";
      } else if (error.response?.status === 429) {
        errorMessage = "Too many verification attempts. Please try again later.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
        step: error.response?.status === 402 ? 'error' : 'phone'
      }));
    }
  };

  const handleVerificationSubmit = async () => {
    if (!state.verificationCode.trim()) {
      setState(prev => ({ ...prev, error: 'Please enter the verification code' }));
      return;
    }

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      await apiClient.post('/api/v1/profile/phone/verify', {
        verification_code: state.verificationCode
      });

      setState(prev => ({
        ...prev,
        loading: false,
        step: 'success'
      }));

      toast({
        title: "Phone verified!",
        description: "You can now send SMS commands to Jean Memory",
      });

    } catch (error: any) {
      let errorMessage = "Invalid verification code";
      
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }

      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage
      }));
    }
  };

  const formatPhoneNumber = (value: string) => {
    // Remove all non-digit characters
    const digits = value.replace(/\D/g, '');
    
    // Format as (XXX) XXX-XXXX
    if (digits.length <= 3) {
      return digits;
    } else if (digits.length <= 6) {
      return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
    } else {
      return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
    }
  };

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatPhoneNumber(e.target.value);
    setState(prev => ({ ...prev, phoneNumber: formatted, error: null }));
  };

  const renderPhoneStep = () => (
    <>
      <div className="sm:contents max-sm:space-y-4">
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-4">
            <MessageSquare className="w-8 h-8 text-blue-500" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            Text Jean Memory
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            Connect your phone to text your personal AI memory assistant anytime, anywhere
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="phone" className="text-sm font-medium">
              Phone Number *
            </Label>
            <Input
              id="phone"
              type="tel"
              placeholder="(555) 123-4567"
              value={state.phoneNumber}
              onChange={handlePhoneChange}
              className="text-center text-lg"
              maxLength={14}
            />
            <p className="text-xs text-muted-foreground text-center">
              US phone numbers only. Message & data rates may apply.
            </p>
          </div>

          {state.error && (
            <Alert variant="destructive">
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}

          <div className="bg-muted/50 rounded-lg p-4 space-y-2">
            <h4 className="font-medium text-sm flex items-center gap-2">
              <Smartphone className="w-4 h-4" />
              Text Your Memory Assistant:
            </h4>
            <div className="text-xs text-muted-foreground space-y-1">
              <div>Text like you're talking to a trusted friend who remembers everything!</div>
              <div>• "Remember I had a great meeting with Sarah today"</div>
              <div>• "What do I remember about my anxiety triggers?"</div>
              <div>• "How do my work meetings usually go?"</div>
              <div>• "Analyze patterns in my mood over time"</div>
              <div>• Text "help" anytime for more examples.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-4 max-sm:flex-col max-sm:space-y-2 max-sm:px-4 max-sm:pb-4 max-sm:bg-background max-sm:border-t max-sm:border-border max-sm:-mx-4 max-sm:-mb-4 max-sm:mt-4">
        <Button variant="outline" onClick={handleClose} className="flex-1">
          Cancel
        </Button>
        <Button onClick={handlePhoneSubmit} className="flex-1" disabled={state.loading}>
          {state.loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Sending...
            </>
          ) : (
            'Send Code'
          )}
        </Button>
      </div>
    </>
  );

  const renderVerificationStep = () => (
    <>
      <div className="sm:contents max-sm:space-y-4">
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-green-500/10 border border-green-500/20 flex items-center justify-center mb-4">
            <Shield className="w-8 h-8 text-green-500" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            Verify Your Phone
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            Enter the 6-digit code sent to {state.phoneNumber}
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="code" className="text-sm font-medium">
              Verification Code *
            </Label>
            <Input
              id="code"
              type="text"
              placeholder="123456"
              value={state.verificationCode}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                setState(prev => ({ ...prev, verificationCode: value, error: null }));
              }}
              className="text-center text-2xl font-mono tracking-widest"
              maxLength={6}
              disabled={state.loading}
            />
            <p className="text-xs text-muted-foreground text-center">
              Code expires in {state.expiresInMinutes} minutes
            </p>
          </div>

          {state.error && (
            <Alert variant="destructive">
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}
        </div>
      </div>

      <div className="flex gap-2 pt-4 max-sm:flex-col max-sm:space-y-2 max-sm:px-4 max-sm:pb-4 max-sm:bg-background max-sm:border-t max-sm:border-border max-sm:-mx-4 max-sm:-mb-4 max-sm:mt-4">
        <Button variant="outline" onClick={() => setState(prev => ({ ...prev, step: 'phone' }))} className="flex-1" disabled={state.loading}>
          Back
        </Button>
        <Button onClick={handleVerificationSubmit} className="flex-1" disabled={state.loading}>
          {state.loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Verifying...
            </>
          ) : (
            'Verify'
          )}
        </Button>
      </div>
    </>
  );

  const renderSuccessStep = () => (
    <>
      <div className="sm:contents max-sm:space-y-4">
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-green-500/10 border border-green-500/20 flex items-center justify-center mb-4">
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            SMS Connected!
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            You can now text Jean Memory to manage your memories
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <div className="space-y-4 py-2">
          <div className="bg-green-50 dark:bg-green-500/10 rounded-lg p-4 space-y-2">
            <h4 className="font-medium text-sm text-green-800 dark:text-green-400">
              🎉 Ready to use! Try sending:
            </h4>
            <div className="text-sm text-green-700 dark:text-green-300 space-y-1">
              <div>• <code>remember: Jean Memory SMS is working!</code></div>
              <div>• <code>search: working</code></div>
              <div>• <code>help</code> for all commands</div>
            </div>
          </div>

          <Alert>
            <AlertDescription className="text-sm">
              <strong>📱 Contact Card Sent:</strong> Check your messages! I've sent you my contact card so you can easily save my number to your phone. You have 50 SMS commands per day with your Pro subscription.
            </AlertDescription>
          </Alert>
        </div>
      </div>

      <div className="pt-4 max-sm:px-4 max-sm:pb-4 max-sm:bg-background max-sm:border-t max-sm:border-border max-sm:-mx-4 max-sm:-mb-4 max-sm:mt-4">
        <Button onClick={handleClose} className="w-full">
          Done
        </Button>
      </div>
    </>
  );

  const renderErrorStep = () => (
    <>
      <div className="sm:contents max-sm:space-y-4">
        <MobileOptimizedDialogHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
            <MessageSquare className="w-8 h-8 text-red-500" />
          </div>
          <MobileOptimizedDialogTitle className="text-2xl font-bold">
            Upgrade Required
          </MobileOptimizedDialogTitle>
          <MobileOptimizedDialogDescription className="text-muted-foreground pt-1">
            SMS features are available with Jean Memory Pro
          </MobileOptimizedDialogDescription>
        </MobileOptimizedDialogHeader>

        <div className="space-y-4 py-2">
          {state.error && (
            <Alert variant="destructive">
              <AlertDescription>{state.error}</AlertDescription>
            </Alert>
          )}

          <div className="bg-muted/50 rounded-lg p-4 space-y-2">
            <h4 className="font-medium text-sm">Pro includes:</h4>
            <div className="text-sm text-muted-foreground space-y-1">
              <div>• 50 SMS commands per day</div>
              <div>• Unlimited API access</div>
              <div>• Advanced memory features</div>
              <div>• Priority support</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-4 max-sm:flex-col max-sm:space-y-2 max-sm:px-4 max-sm:pb-4 max-sm:bg-background max-sm:border-t max-sm:border-border max-sm:-mx-4 max-sm:-mb-4 max-sm:mt-4">
        <Button variant="outline" onClick={handleClose} className="flex-1">
          Cancel
        </Button>
        <Button 
          onClick={() => window.open('/pro', '_blank')} 
          className="flex-1"
        >
          Upgrade to Pro
        </Button>
      </div>
    </>
  );

  const renderStep = () => {
    switch (state.step) {
      case 'phone':
        return renderPhoneStep();
      case 'verification':
        return renderVerificationStep();
      case 'success':
        return renderSuccessStep();
      case 'error':
        return renderErrorStep();
      default:
        return renderPhoneStep();
    }
  };

  return (
    <MobileOptimizedDialog open={open} onOpenChange={handleClose}>
      <MobileOptimizedDialogContent 
        className="sm:max-w-md bg-background border-border shadow-2xl"
        onOpenChange={handleClose}
      >
        {renderStep()}
      </MobileOptimizedDialogContent>
    </MobileOptimizedDialog>
  );
} 