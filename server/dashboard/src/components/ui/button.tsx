import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 font-fustat font-semibold",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground  hover:bg-primary/90",
        destructive:
          "bg-onSurface-danger-primary hover:bg-onSurface-danger-secondary dark:bg-onSurface-danger-secondary dark:hover:bg-onSurface-danger-primary text-white",
        outline:
          "border border-memBorder-primary bg-surface-default-primary hover:bg-neutral-100 hover:text-neutral-800",
        secondary:
          "bg-surface-default-fg-secondary text-onSurface-default-primary hover:bg-surface-default-fg-secondary-hover border border-memBorder-primary",
        ghost: "hover:bg-accent/30 hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        grey: "bg-accent/30 text-accent-foreground hover:bg-accent/80",
        primary:
          "bg-onSurface-default-primary text-surface-default-primary hover:bg-onSurface-default-primary/80",
        tertiary:
          "bg-surface-default-tertiary text-onSurface-default-primary hover:bg-surface-default-tertiary-hover",
        surfaceSecondary:
          "bg-surface-default-secondary text-onSurface-default-primary hover:bg-surface-default-secondary-hover border border-memBorder-primary",
        surfacePrimary:
          "bg-surface-default-primary text-onSurface-default-primary hover:bg-surface-default-primary-hover",
        transparent:
          "bg-transparent text-onSurface-default-primary hover:bg-transparent/80 hover:text-white",
        subtle:
          "bg-transparent text-onSurface-default-primary hover:bg-surface-default-fg-secondary-hover border-0",
        brand:
          "bg-surface-default-brand text-onSurface-default-primary hover:bg-surface-default-brand-hover",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-lg px-8",
        icon: "size-9",
        xl: "h-16 rounded-md px-5 ",
        xs: "h-[30px] px-3 text-[10px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
export type { ButtonProps };
