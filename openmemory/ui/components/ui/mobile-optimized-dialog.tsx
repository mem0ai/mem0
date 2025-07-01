"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface SwipeToCloseProps {
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}

function SwipeToClose({ onClose, children, className }: SwipeToCloseProps) {
  const [startY, setStartY] = React.useState<number | null>(null);
  const [currentY, setCurrentY] = React.useState<number | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);

  const handleTouchStart = (e: React.TouchEvent) => {
    // Don't interfere with button/input clicks
    if ((e.target as HTMLElement).closest('button, input, textarea, select, [role="button"]')) {
      return;
    }
    
    setStartY(e.touches[0].clientY);
    setIsDragging(true);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (!startY || !isDragging) return;
    
    const currentY = e.touches[0].clientY;
    setCurrentY(currentY);
    
    // Only allow downward swipes and only if significant movement
    const deltaY = Math.max(0, currentY - startY);
    
    if (deltaY > 10) { // Only start visual feedback after 10px movement
      // Apply transform for visual feedback
      const element = e.currentTarget as HTMLElement;
      element.style.transform = `translateY(${deltaY * 0.5}px)`;
      element.style.opacity = `${Math.max(0.3, 1 - (deltaY / 300))}`;
    }
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!startY || !currentY || !isDragging) {
      setStartY(null);
      setCurrentY(null);
      setIsDragging(false);
      return;
    }

    const deltaY = currentY - startY;
    const element = e.currentTarget as HTMLElement;
    
    if (deltaY > 100) { // Threshold for closing
      onClose();
    } else {
      // Reset position with animation
      element.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
      element.style.transform = 'translateY(0px)';
      element.style.opacity = '1';
      
      // Clean up transition after animation
      setTimeout(() => {
        element.style.transition = '';
      }, 200);
    }
    
    setStartY(null);
    setCurrentY(null);
    setIsDragging(false);
  };

  return (
    <div
      className={className}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {children}
    </div>
  );
}

const MobileOptimizedDialog = DialogPrimitive.Root;

const MobileOptimizedDialogTrigger = DialogPrimitive.Trigger;

const MobileOptimizedDialogPortal = DialogPrimitive.Portal;

const MobileOptimizedDialogClose = DialogPrimitive.Close;

const MobileOptimizedDialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
));
MobileOptimizedDialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const MobileOptimizedDialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    showCloseButton?: boolean;
    mobileFullScreen?: boolean;
    onOpenChange?: (open: boolean) => void;
  }
>(({ className, children, showCloseButton = true, mobileFullScreen = false, onOpenChange, ...props }, ref) => (
  <MobileOptimizedDialogPortal>
    <MobileOptimizedDialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        // Base styles - keep original grid layout and max-w-lg
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]",
        
        // Desktop styles - keep original padding
        "sm:rounded-lg sm:p-6 sm:max-h-[90vh] sm:overflow-y-auto",
        
        // Mobile styles - conditional full screen or bottom sheet
        mobileFullScreen 
          ? "max-sm:h-full max-sm:w-full max-sm:rounded-none max-sm:border-0 max-sm:p-4 max-sm:overflow-y-auto" 
          : "max-sm:fixed max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:top-auto max-sm:translate-x-0 max-sm:translate-y-0 max-sm:rounded-t-xl max-sm:rounded-b-none max-sm:border-x-0 max-sm:border-b-0 max-sm:max-h-[85vh] max-sm:p-0 max-sm:data-[state=open]:slide-in-from-bottom max-sm:data-[state=closed]:slide-out-to-bottom max-sm:flex max-sm:flex-col",
        
        className
      )}
      {...props}
    >
      {/* Mobile swipe indicator */}
      <div className="sm:hidden flex justify-center pt-2 pb-2 px-4 flex-shrink-0">
        <div className="w-12 h-1 bg-muted-foreground/30 rounded-full" />
      </div>
      
      {/* Scrollable content area on mobile */}
      <div className="sm:contents max-sm:flex-1 max-sm:overflow-y-auto max-sm:px-4">
        <SwipeToClose onClose={() => onOpenChange?.(false)}>
          <div className="sm:contents max-sm:min-h-0">
            {children}
          </div>
        </SwipeToClose>
      </div>
      
      {/* Close button - same as original but mobile optimized */}
      {showCloseButton && (
        <DialogPrimitive.Close className={cn(
          "absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground z-10",
          // Larger touch target on mobile
          "max-sm:right-3 max-sm:top-3 max-sm:h-8 max-sm:w-8 max-sm:flex max-sm:items-center max-sm:justify-center max-sm:bg-muted/80 max-sm:rounded-full max-sm:backdrop-blur-sm"
        )}>
          <X className="h-4 w-4 max-sm:h-5 max-sm:w-5" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </MobileOptimizedDialogPortal>
));
MobileOptimizedDialogContent.displayName = DialogPrimitive.Content.displayName;

const MobileOptimizedDialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-1.5 text-center sm:text-left",
      className
    )}
    {...props}
  />
);
MobileOptimizedDialogHeader.displayName = "MobileOptimizedDialogHeader";

const MobileOptimizedDialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      // Mobile-optimized button layout
      "max-sm:space-y-2 max-sm:space-y-reverse max-sm:pt-4",
      className
    )}
    {...props}
  />
);
MobileOptimizedDialogFooter.displayName = "MobileOptimizedDialogFooter";

const MobileOptimizedDialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      "text-lg font-semibold leading-none tracking-tight",
      // Larger text on mobile for better readability
      "max-sm:text-xl",
      className
    )}
    {...props}
  />
));
MobileOptimizedDialogTitle.displayName = DialogPrimitive.Title.displayName;

const MobileOptimizedDialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn(
      "text-sm text-muted-foreground",
      // Better mobile spacing
      "max-sm:text-base max-sm:leading-relaxed",
      className
    )}
    {...props}
  />
));
MobileOptimizedDialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  MobileOptimizedDialog,
  MobileOptimizedDialogPortal,
  MobileOptimizedDialogOverlay,
  MobileOptimizedDialogClose,
  MobileOptimizedDialogTrigger,
  MobileOptimizedDialogContent,
  MobileOptimizedDialogHeader,
  MobileOptimizedDialogFooter,
  MobileOptimizedDialogTitle,
  MobileOptimizedDialogDescription,
}; 