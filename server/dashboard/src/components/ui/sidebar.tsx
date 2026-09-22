"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Slot } from "@radix-ui/react-slot";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const sidebarVariants = cva(
  "relative flex flex-col gap-0 border-r border-memBorder-primary",
  {
    variants: {
      collapsible: {
        icon: "w-[90px] transition-[width] duration-300 ease-in-out",
        default: "w-72 transition-[width] duration-300 ease-in-out",
      },
    },
    defaultVariants: {
      collapsible: "default",
    },
  },
);

interface SidebarProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof sidebarVariants> {}

const Sidebar = React.forwardRef<HTMLDivElement, SidebarProps>(
  ({ className, collapsible, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(sidebarVariants({ collapsible }), className)}
      {...props}
    />
  ),
);
Sidebar.displayName = "Sidebar";

const SidebarHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-2", className)} {...props} />
));
SidebarHeader.displayName = "SidebarHeader";

const SidebarContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-1 flex-col gap-0 overflow-hidden", className)}
    {...props}
  />
));
SidebarContent.displayName = "SidebarContent";

const SidebarFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("mt-auto", className)} {...props} />
));
SidebarFooter.displayName = "SidebarFooter";

const SidebarGroup = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-1", className)} {...props} />
));
SidebarGroup.displayName = "SidebarGroup";

const SidebarGroupLabel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex w-full items-center gap-1 px-[6px] py-1 text-[10px] font-medium uppercase leading-[140%] text-onSurface-default-tertiary font-dm-mono",
      className,
    )}
    {...props}
  />
));
SidebarGroupLabel.displayName = "SidebarGroupLabel";

const SidebarMenu = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-1", className)} {...props} />
));
SidebarMenu.displayName = "SidebarMenu";

const SidebarMenuItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("", className)} {...props} />
));
SidebarMenuItem.displayName = "SidebarMenuItem";

const menuButtonVariants = cva(
  "group flex w-full items-center gap-1.5 rounded p-1.5 font-fustat text-xs font-semibold leading-[140%] transition-colors",
  {
    variants: {
      active: {
        true: "bg-surface-default-tertiary text-onSurface-default-primary [&_svg]:text-onSurface-default-primary",
        false:
          "bg-transparent text-onSurface-default-secondary [&_svg]:text-onSurface-default-tertiary hover:bg-surface-default-primary-hover [&_svg]:group-hover:text-onSurface-default-secondary",
      },
      collapsed: {
        true: "!w-8 !h-8 !p-2 items-center justify-center",
        false: "",
      },
    },
    compoundVariants: [
      {
        collapsed: true,
        active: false,
        className:
          "bg-surface-default-secondary hover:bg-surface-default-primary-hover [&_svg]:text-onSurface-default-tertiary [&_svg]:group-hover:text-onSurface-default-secondary",
      },
      {
        collapsed: true,
        active: true,
        className:
          "bg-surface-default-tertiary [&_svg]:text-onSurface-default-primary",
      },
    ],
    defaultVariants: {
      active: false,
      collapsed: false,
    },
  },
);

interface SidebarMenuButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof menuButtonVariants> {
  asChild?: boolean;
  tooltip?: string;
}

const SidebarMenuButton = React.forwardRef<
  HTMLButtonElement,
  SidebarMenuButtonProps
>(
  (
    { className, active, collapsed, asChild = false, tooltip, ...props },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    const button = (
      <Comp
        ref={ref}
        className={cn(menuButtonVariants({ active, collapsed }), className)}
        {...props}
      />
    );

    if (!tooltip) {
      return button;
    }

    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right">{tooltip}</TooltipContent>
      </Tooltip>
    );
  },
);
SidebarMenuButton.displayName = "SidebarMenuButton";

const SidebarMenuAction = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    showOnHover?: boolean;
  }
>(({ className, showOnHover, ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "flex h-6 w-6 items-center justify-center rounded-md hover:bg-accent hover:text-accent-foreground",
      showOnHover && "invisible group-hover:visible",
      className,
    )}
    {...props}
  />
));
SidebarMenuAction.displayName = "SidebarMenuAction";

const SidebarMenuSub = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col gap-1 py-1.5 pl-6", className)}
    {...props}
  />
));
SidebarMenuSub.displayName = "SidebarMenuSub";

const SidebarMenuSubItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("", className)} {...props} />
));
SidebarMenuSubItem.displayName = "SidebarMenuSubItem";

const SidebarMenuSubButton = React.forwardRef<
  HTMLButtonElement,
  SidebarMenuButtonProps
>(({ className, active, collapsed, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      ref={ref}
      className={cn(
        "group flex w-full items-center gap-1.5 rounded p-1.5 font-fustat text-xs font-semibold leading-[140%] transition-colors",
        active
          ? "bg-surface-default-tertiary text-onSurface-default-primary [&_svg]:text-onSurface-default-primary"
          : "bg-transparent text-onSurface-default-secondary [&_svg]:text-onSurface-default-tertiary hover:bg-surface-default-primary-hover hover:[&_svg]:text-onSurface-default-secondary",
        className,
      )}
      {...props}
    />
  );
});
SidebarMenuSubButton.displayName = "SidebarMenuSubButton";

const SidebarRail = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "absolute right-0 top-0 h-full w-px bg-border opacity-0",
      className,
    )}
    {...props}
  />
));
SidebarRail.displayName = "SidebarRail";

export {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuAction,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  SidebarRail,
};
