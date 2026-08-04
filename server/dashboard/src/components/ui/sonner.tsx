"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      position="bottom-right"
      style={{ zIndex: 10000 }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-surface-default-primary group-[.toaster]:text-foreground group-[.toaster]:border-memBorder-primary group-[.toaster]:shadow-lg group-[.toaster]:rounded-md group-[.toaster]:pointer-events-auto",
          title: "group-[.toast]:text-sm group-[.toast]:font-semibold",
          description:
            "group-[.toast]:text-muted-foreground group-[.toast]:text-sm",
          icon: "hidden",
          success:
            "group-[.toaster]:border-l-4 group-[.toaster]:border-l-[var(--surface-positive-primary)]",
          error:
            "group-[.toaster]:border-l-4 group-[.toaster]:border-l-[var(--surface-danger-primary)]",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
