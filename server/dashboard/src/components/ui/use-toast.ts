"use client";

// Shadcn recommends Sonner for toasts. This module wraps Sonner so existing
// toast({ title, description, variant }) calls work and render via <Toaster /> from @/components/ui/sonner.
import * as React from "react";
import { toast as sonnerToast } from "sonner";

export type ToastVariant = "default" | "destructive" | "success";

export type ToastOptions = {
  title?: React.ReactNode;
  description?: React.ReactNode;
  variant?: ToastVariant;
};

function toast(options: ToastOptions) {
  const { title, description, variant = "default" } = options;
  const message =
    title != null
      ? String(title)
      : description != null
        ? String(description)
        : "Notification";
  const opts =
    title != null && description != null
      ? { description: String(description) }
      : {};

  if (variant === "destructive") {
    sonnerToast.error(message, opts);
  } else if (variant === "success") {
    sonnerToast.success(message, opts);
  } else {
    sonnerToast(message, opts);
  }

  return {
    id: "",
    dismiss: () => {},
    update: () => {},
  };
}

function useToast() {
  return React.useMemo(
    () => ({
      toasts: [],
      toast,
      dismiss: () => {},
    }),
    [],
  );
}

export { sonnerToast as toastSonner };
export { useToast, toast };
